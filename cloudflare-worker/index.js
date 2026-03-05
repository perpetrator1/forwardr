/**
 * Cloudflare Worker for Forwardr
 *
 * Responsibilities:
 * 1. Receive Telegram webhook updates and forward to Render FastAPI backend
 * 2. Owner-only filtering — only process messages from TELEGRAM_OWNER_ID
 * 3. Handle Telegram bot commands (/setcred, /getcreds, /status, /help)
 *    and store credentials in Cloudflare KV
 * 4. Cron trigger — wake the Render server and process the queue every 5 hours
 * 5. Expose /credentials endpoint so the Render server can fetch stored creds
 */

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Extract the message object from a Telegram update payload.
 */
function getMessage(payload) {
  return (
    payload.message ||
    payload.edited_message ||
    payload.channel_post ||
    payload.edited_channel_post ||
    null
  );
}

/**
 * Extract the sender's Telegram user ID (as string) from an update.
 */
function getSenderId(payload) {
  const message = getMessage(payload);
  if (!message) return null;
  return message.from ? String(message.from.id) : null;
}

/**
 * Extract the chat ID to reply to.
 */
function getChatId(payload) {
  const message = getMessage(payload);
  if (!message) return null;
  return message.chat ? String(message.chat.id) : null;
}

/**
 * Send a text message back to a Telegram chat.
 */
async function sendTelegramMessage(botToken, chatId, text) {
  const url = `https://api.telegram.org/bot${botToken}/sendMessage`;
  await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      chat_id: chatId,
      text: text,
      parse_mode: "Markdown",
    }),
  });
}

// ---------------------------------------------------------------------------
// Credential management via KV
// ---------------------------------------------------------------------------

/**
 * Known credential keys per platform.
 * Used for validation and display.
 */
const PLATFORM_KEYS = {
  telegram: ["bot_token", "chat_id"],
  bluesky: ["handle", "password"],
  mastodon: ["instance_url", "access_token"],
  instagram: ["access_token", "business_account_id"],
  threads: ["access_token", "user_id"],
  twitter: [
    "api_key",
    "api_secret",
    "access_token",
    "access_token_secret",
    "bearer_token",
  ],
  reddit: [
    "client_id",
    "client_secret",
    "username",
    "password",
    "user_agent",
    "subreddit",
    "default_title",
  ],
  youtube: ["client_secrets_file", "token_file"],
  cloudinary: ["cloud_name", "api_key", "api_secret"],
};

/**
 * Store a credential in KV.  Key format: `cred:<platform>:<key>`
 */
async function setCredential(kvNamespace, platform, key, value) {
  const kvKey = `cred:${platform}:${key}`;
  await kvNamespace.put(kvKey, value);
}

/**
 * Get a single credential from KV.
 */
async function getCredential(kvNamespace, platform, key) {
  const kvKey = `cred:${platform}:${key}`;
  return await kvNamespace.get(kvKey);
}

/**
 * Get all credentials — returns { platform: { key: value, ... }, ... }
 */
async function getAllCredentials(kvNamespace) {
  const result = {};
  const list = await kvNamespace.list({ prefix: "cred:" });

  for (const item of list.keys) {
    const raw = await kvNamespace.get(item.name);
    if (raw === null) continue;

    // Parse key format: cred:<platform>:<key>
    const parts = item.name.split(":");
    if (parts.length < 3) continue;

    const platform = parts[1];
    const key = parts.slice(2).join(":"); // handle keys with colons

    if (!result[platform]) result[platform] = {};
    result[platform][key] = raw;
  }

  return result;
}

/**
 * List which platforms have at least one credential set.
 * Returns an object: { platform: [key1, key2, ...], ... }
 */
async function listConfiguredPlatforms(kvNamespace) {
  const result = {};
  const list = await kvNamespace.list({ prefix: "cred:" });

  for (const item of list.keys) {
    const parts = item.name.split(":");
    if (parts.length < 3) continue;

    const platform = parts[1];
    const key = parts.slice(2).join(":");

    if (!result[platform]) result[platform] = [];
    result[platform].push(key);
  }

  return result;
}

// ---------------------------------------------------------------------------
// Telegram command handling
// ---------------------------------------------------------------------------

async function handleCommand(env, chatId, text) {
  const parts = text.trim().split(/\s+/);
  const command = parts[0].toLowerCase().replace(/@\w+$/, ""); // strip @botname

  switch (command) {
    case "/setcred": {
      // /setcred <platform> <key> <value>
      if (parts.length < 4) {
        return (
          "❌ *Usage:* `/setcred <platform> <key> <value>`\n\n" +
          "*Example:*\n`/setcred bluesky handle your-handle.bsky.social`\n\n" +
          "*Platforms:* " +
          Object.keys(PLATFORM_KEYS).join(", ")
        );
      }

      const platform = parts[1].toLowerCase();
      const key = parts[2].toLowerCase();
      const value = parts.slice(3).join(" ");

      if (!PLATFORM_KEYS[platform]) {
        return (
          `❌ Unknown platform: \`${platform}\`\n\n` +
          "*Valid platforms:* " +
          Object.keys(PLATFORM_KEYS).join(", ")
        );
      }

      if (!env.CREDENTIALS) {
        return "❌ Credentials KV namespace not configured.";
      }

      await setCredential(env.CREDENTIALS, platform, key, value);
      return `✅ Set \`${platform}.${key}\` successfully.`;
    }

    case "/delcred": {
      // /delcred <platform> <key>
      if (parts.length < 3) {
        return "❌ *Usage:* `/delcred <platform> <key>`";
      }

      const platform = parts[1].toLowerCase();
      const key = parts[2].toLowerCase();

      if (!env.CREDENTIALS) {
        return "❌ Credentials KV namespace not configured.";
      }

      const kvKey = `cred:${platform}:${key}`;
      await env.CREDENTIALS.delete(kvKey);
      return `🗑️ Deleted \`${platform}.${key}\`.`;
    }

    case "/getcreds": {
      if (!env.CREDENTIALS) {
        return "❌ Credentials KV namespace not configured.";
      }

      const configured = await listConfiguredPlatforms(env.CREDENTIALS);
      const platformNames = Object.keys(configured);

      if (platformNames.length === 0) {
        return "📋 No credentials configured yet.\n\nUse `/setcred <platform> <key> <value>` to add credentials.";
      }

      let msg = "📋 *Configured Platforms:*\n\n";
      for (const platform of platformNames) {
        const keys = configured[platform];
        const required = PLATFORM_KEYS[platform] || [];
        const missing = required.filter((k) => !keys.includes(k));

        const statusIcon = missing.length === 0 ? "✅" : "⚠️";
        msg += `${statusIcon} *${platform}*: ${keys.join(", ")}`;

        if (missing.length > 0) {
          msg += `\n   _Missing:_ ${missing.join(", ")}`;
        }
        msg += "\n";
      }

      return msg;
    }

    case "/status": {
      // Fetch queue status from the Render server
      try {
        const healthUrl = `${env.RENDER_URL.replace(/\/$/, "")}/health`;
        const resp = await fetch(healthUrl, { signal: AbortSignal.timeout(10000) });

        if (!resp.ok) {
          return `⚠️ Server responded with status ${resp.status}. It may be spinning up — try again in a minute.`;
        }

        const health = await resp.json();
        let msg = "📊 *Server Status*\n\n";
        msg += `Status: ${health.status}\n`;

        if (health.queue) {
          msg += `\n*Queue:*\n`;
          msg += `  Pending: ${health.queue.pending || 0}\n`;
          msg += `  Completed: ${health.queue.completed || 0}\n`;
          msg += `  Failed: ${health.queue.failed || 0}\n`;
          msg += `  Total: ${health.queue.total || 0}\n`;
        }

        if (health.enabled_platforms && health.enabled_platforms.length > 0) {
          msg += `\n*Enabled platforms:* ${health.enabled_platforms.join(", ")}`;
        }

        return msg;
      } catch (e) {
        return "⚠️ Could not reach the server. It may be spinning up — try again in a minute.";
      }
    }

    case "/start": {
      return (
        "Wassup Twin\n\n" +
        "Send me a photo, video, or text and I'll post it to all your configured platforms at once.\n\n" +
        "Use /help to see all available commands."
      );
    }

    case "/help": {
      return (
        "🤖 *Forwardr Bot Commands*\n\n" +
        "📬 *Posting:*\nSend a photo, video, or text to queue it for posting to all configured platforms.\n\n" +
        "🔑 *Credential Management:*\n" +
        "`/setcred <platform> <key> <value>` — Save a credential\n" +
        "`/delcred <platform> <key>` — Delete a credential\n" +
        "`/getcreds` — List configured platforms\n\n" +
        "📊 *Status:*\n" +
        "`/status` — Show queue & server status\n" +
        "`/help` — Show this help message\n\n" +
        "*Supported platforms:*\n" +
        Object.keys(PLATFORM_KEYS).join(", ")
      );
    }

    default:
      return null; // Not a recognized command
  }
}

// ---------------------------------------------------------------------------
// Render forwarding
// ---------------------------------------------------------------------------

async function forwardToRender(env, payload) {
  if (!env.RENDER_URL || !env.API_KEY) {
    throw new Error("Missing RENDER_URL or API_KEY secrets");
  }

  const wakeUrl = env.RENDER_URL;
  const webhookUrl = `${env.RENDER_URL.replace(/\/$/, "")}/webhook`;

  // Wake the server
  await fetch(wakeUrl, { method: "GET" });

  const response = await fetch(webhookUrl, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-API-Key": env.API_KEY,
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(`Render webhook failed: ${response.status} ${text}`);
  }
}

async function triggerQueueProcessing(env) {
  if (!env.RENDER_URL || !env.API_KEY) {
    throw new Error("Missing RENDER_URL or API_KEY secrets");
  }

  await fetch(env.RENDER_URL, { method: "GET" });

  const processUrl = `${env.RENDER_URL.replace(/\/$/, "")}/process-queue`;
  const response = await fetch(processUrl, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-API-Key": env.API_KEY,
    },
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(`Queue processing failed: ${response.status} ${text}`);
  }

  return await response.json();
}

// ---------------------------------------------------------------------------
// Failed update storage & replay
// ---------------------------------------------------------------------------

async function storeFailed(env, updateId, payload) {
  if (!env.FAILED_UPDATES) return;
  const key = `failed:${updateId}`;
  await env.FAILED_UPDATES.put(key, JSON.stringify(payload));
}

async function replayFailed(env) {
  if (!env.FAILED_UPDATES) {
    return { replayed: 0, failed: 0, remaining: 0 };
  }

  const list = await env.FAILED_UPDATES.list({ prefix: "failed:" });
  let replayed = 0;
  let failed = 0;

  for (const item of list.keys) {
    const raw = await env.FAILED_UPDATES.get(item.name);
    if (!raw) continue;

    let payload;
    try {
      payload = JSON.parse(raw);
    } catch {
      await env.FAILED_UPDATES.delete(item.name);
      continue;
    }

    try {
      await forwardToRender(env, payload);
      await env.FAILED_UPDATES.delete(item.name);
      replayed += 1;
    } catch {
      failed += 1;
    }
  }

  const remaining = (await env.FAILED_UPDATES.list({ prefix: "failed:" })).keys
    .length;
  return { replayed, failed, remaining };
}

// ---------------------------------------------------------------------------
// Worker export
// ---------------------------------------------------------------------------

export default {
  /**
   * HTTP request handler — Telegram webhook, /retry, /credentials
   */
  async fetch(request, env, ctx) {
    const url = new URL(request.url);

    // GET /retry — replay failed updates
    if (request.method === "GET" && url.pathname === "/retry") {
      const summary = await replayFailed(env);
      return new Response(JSON.stringify(summary), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }

    // GET /credentials — return all stored credentials (API-key protected)
    if (request.method === "GET" && url.pathname === "/credentials") {
      const apiKey = request.headers.get("X-API-Key");
      if (!env.API_KEY || apiKey !== env.API_KEY) {
        return new Response("Unauthorized", { status: 401 });
      }

      if (!env.CREDENTIALS) {
        return new Response(JSON.stringify({}), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }

      const creds = await getAllCredentials(env.CREDENTIALS);
      return new Response(JSON.stringify(creds), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }

    // Only process POST from here on (Telegram webhook)
    if (request.method !== "POST") {
      return new Response("OK", { status: 200 });
    }

    let payload;
    try {
      payload = await request.json();
    } catch {
      return new Response("OK", { status: 200 });
    }

    const updateId = payload && payload.update_id;
    if (!updateId) {
      return new Response("OK", { status: 200 });
    }

    // Owner-only filter
    if (env.TELEGRAM_OWNER_ID) {
      const senderId = getSenderId(payload);
      if (senderId && senderId !== String(env.TELEGRAM_OWNER_ID)) {
        return new Response("OK", { status: 200 });
      }
    }

    // Check if this is a bot command
    const message = getMessage(payload);
    const messageText = message && (message.text || "");
    const chatId = getChatId(payload);

    if (messageText.startsWith("/") && chatId && env.TELEGRAM_BOT_TOKEN) {
      // Handle command in the background
      ctx.waitUntil(
        (async () => {
          try {
            const response = await handleCommand(env, chatId, messageText);
            if (response) {
              await sendTelegramMessage(env.TELEGRAM_BOT_TOKEN, chatId, response);
            }
          } catch (err) {
            console.error("Command handling error:", err.message);
            await sendTelegramMessage(
              env.TELEGRAM_BOT_TOKEN,
              chatId,
              "❌ An error occurred processing your command."
            );
          }
        })()
      );
      return new Response("OK", { status: 200 });
    }

    // Not a command — forward media/text to Render for queuing
    ctx.waitUntil(
      (async () => {
        try {
          await forwardToRender(env, payload);
        } catch (err) {
          await storeFailed(env, updateId, payload);
        }
      })()
    );

    return new Response("OK", { status: 200 });
  },

  /**
   * Cron trigger — processes the queue every 5 hours
   */
  async scheduled(event, env, ctx) {
    ctx.waitUntil(
      (async () => {
        try {
          const result = await triggerQueueProcessing(env);
          console.log("Queue processing result:", JSON.stringify(result));
        } catch (err) {
          console.error("Queue processing failed:", err.message);
        }
      })()
    );
  },
};
