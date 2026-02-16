/**
 * Cloudflare Worker to receive Telegram webhooks and forward to FastAPI backend.
 */

async function forwardToRender(env, payload) {
  if (!env.RENDER_URL || !env.API_KEY) {
    throw new Error("Missing RENDER_URL or API_KEY secrets");
  }

  const wakeUrl = env.RENDER_URL;
  const webhookUrl = `${env.RENDER_URL.replace(/\/$/, "")}/webhook`;

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

async function storeFailed(env, updateId, payload) {
  if (!env.FAILED_UPDATES) {
    return;
  }
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
    if (!raw) {
      continue;
    }

    let payload;
    try {
      payload = JSON.parse(raw);
    } catch (err) {
      await env.FAILED_UPDATES.delete(item.name);
      continue;
    }

    try {
      await forwardToRender(env, payload);
      await env.FAILED_UPDATES.delete(item.name);
      replayed += 1;
    } catch (err) {
      failed += 1;
    }
  }

  const remaining = (await env.FAILED_UPDATES.list({ prefix: "failed:" })).keys.length;
  return { replayed, failed, remaining };
}

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);

    if (request.method === "GET" && url.pathname === "/retry") {
      const summary = await replayFailed(env);
      return new Response(JSON.stringify(summary), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }

    if (request.method !== "POST") {
      return new Response("OK", { status: 200 });
    }

    let payload;
    try {
      payload = await request.json();
    } catch (err) {
      return new Response("OK", { status: 200 });
    }

    const updateId = payload && payload.update_id;
    if (!updateId) {
      return new Response("OK", { status: 200 });
    }

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
};
