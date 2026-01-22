import { Context } from "hono";
import { getCookie } from "hono/cookie";
import { verifySession, SESSION_COOKIE } from "../auth/session";

// Track active WebSocket connections
const connections = new Set<WebSocket>();

/**
 * WebSocket handler for real-time updates.
 */
export async function wsHandler(c: Context) {
  // Verify auth
  const token = getCookie(c, SESSION_COOKIE) || c.req.query("token");
  if (!token) {
    return c.json({ error: "Unauthorized" }, 401);
  }

  const session = await verifySession(token);
  if (!session) {
    return c.json({ error: "Invalid session" }, 401);
  }

  // Upgrade to WebSocket
  const upgradeHeader = c.req.header("Upgrade");
  if (!upgradeHeader || upgradeHeader !== "websocket") {
    return c.json({ error: "Expected websocket upgrade" }, 426);
  }

  // Use Bun's WebSocket
  const { socket, response } = Bun.upgrade(c.req.raw, {
    data: { adminId: session.telegramId },
  });

  return response;
}

/**
 * Bun WebSocket handlers.
 */
export const websocket = {
  open(ws: WebSocket) {
    connections.add(ws);
    console.log("WebSocket connected, total:", connections.size);
  },

  close(ws: WebSocket) {
    connections.delete(ws);
    console.log("WebSocket disconnected, total:", connections.size);
  },

  message(ws: WebSocket, message: string) {
    try {
      const data = JSON.parse(message);
      handleWsMessage(ws, data);
    } catch (e) {
      console.error("Invalid WebSocket message:", e);
    }
  },
};

/**
 * Handle incoming WebSocket messages.
 */
function handleWsMessage(ws: WebSocket, data: any) {
  switch (data.type) {
    case "subscribe":
      // Subscribe to a channel (not implemented yet)
      break;
    case "unsubscribe":
      // Unsubscribe from a channel
      break;
    default:
      console.log("Unknown WebSocket message type:", data.type);
  }
}

/**
 * Broadcast a message to all connected clients.
 */
export function broadcast(type: string, payload: any) {
  const message = JSON.stringify({ type, payload });

  for (const ws of connections) {
    try {
      ws.send(message);
    } catch (e) {
      // Remove dead connections
      connections.delete(ws);
    }
  }
}

/**
 * Broadcast generation progress update.
 */
export function broadcastGenerationProgress(progress: any) {
  broadcast("generation_progress", progress);
}

/**
 * Broadcast pool health update.
 */
export function broadcastPoolUpdate(stats: any) {
  broadcast("pool_update", stats);
}

/**
 * Broadcast new activity.
 */
export function broadcastActivity(activity: any) {
  broadcast("new_activity", activity);
}
