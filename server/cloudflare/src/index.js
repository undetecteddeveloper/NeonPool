// NeonPool relay on Cloudflare: room codes, and whole game frames passed between a host and its
// guest. It never reads a frame and runs no physics or rules. One Durable Object per room code.
// The protocol (v1) is in docs/ARCHITECTURE.md (network play); server/local_relay.py is the same
// relay in Python, and tests/test_net_relay.py checks both (NEONPOOL_RELAY_TEST_URL=ws://...).

const API = "/v1";
const LETTERS = "ABCDEFGHJKMNPQRSTUVWXYZ"; // game/config.py NET_ROOM_LETTERS (no I, L, O)
const CODE_LEN = 4;
const HOST_GRACE_MS = 90_000; // a host whose link broke has this long to take the room back
const GUEST_STALE_MS = 4_000; // a guest silent this long gives its place to whoever comes in
const ROOM_IDLE_MS = 30 * 60_000; // a room nobody has come into for this long is closed
const TEXT_MAX = 512; // longest text message taken from a player
const BINARY_MAX = 4096; // longest frame message (the game's MAX_FRAME is 1024)
const LAN_MAX = 300;
const CLOSE_HOST_AWAY = 4000; // the guest's link is closed because the host's broke

const isCode = (code) =>
  typeof code === "string" &&
  code.length === CODE_LEN &&
  [...code].every((ch) => LETTERS.includes(ch));

function newCode() {
  const bytes = crypto.getRandomValues(new Uint8Array(CODE_LEN));
  return [...bytes].map((b) => LETTERS[b % LETTERS.length]).join(""); // (23 letters: tiny bias)
}

function hex(n) {
  return [...crypto.getRandomValues(new Uint8Array(n))]
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

function sameText(a, b) {
  const x = new TextEncoder().encode(a);
  const y = new TextEncoder().encode(b);
  return x.byteLength === y.byteLength && crypto.subtle.timingSafeEqual(x, y);
}

const json = (body) =>
  new Response(JSON.stringify(body), { headers: { "content-type": "application/json" } });

// A word of the relay's own (an object, sent as JSON text) or a frame passed on as it came.
function send(ws, word) {
  if (!ws) return;
  try {
    ws.send(typeof word === "object" && word.byteLength === undefined ? JSON.stringify(word) : word);
  } catch {
    // (it has just closed)
  }
}

function hangUp(ws, code = 1000) {
  if (!ws) return;
  try {
    ws.close(code, "");
  } catch {
    // (already closed)
  }
}

// A WebSocket that only says why it cannot go on, then closes.
function refuse(why) {
  const [client, server] = Object.values(new WebSocketPair());
  server.accept();
  send(server, { t: "error", why });
  hangUp(server);
  return new Response(null, { status: 101, webSocket: client });
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const code = url.searchParams.get("code");
    const room = (c) => env.ROOMS.get(env.ROOMS.idFromName(c), { locationHint: "apac" });
    if (url.pathname === "/") return new Response("neonpool relay 1\n");
    if (url.pathname === `${API}/look`) {
      if (!isCode(code)) return json({ ok: false, why: "bad_code" });
      return room(code).fetch(request);
    }
    if (url.pathname !== `${API}/host` && url.pathname !== `${API}/join`) {
      return new Response("no such thing\n", { status: 404 });
    }
    if (request.headers.get("Upgrade") !== "websocket") {
      return new Response("a WebSocket is expected\n", { status: 426 });
    }
    if (url.pathname === `${API}/join`) {
      return isCode(code) ? room(code).fetch(request) : refuse("bad_code");
    }
    if (code !== null) {
      return isCode(code) ? room(code).fetch(request) : refuse("gone");
    }
    for (let i = 0; i < 12; i++) {
      const fresh = newCode();
      const ask = new URL(request.url);
      ask.searchParams.set("code", fresh);
      ask.searchParams.set("new", "1");
      const answer = await room(fresh).fetch(new Request(ask, request));
      if (answer.status !== 409) return answer;
    }
    return new Response("no free code\n", { status: 503 });
  },
};

export class Room {
  constructor(ctx, env) {
    this.ctx = ctx;
    this.rec = undefined; // {code, key, lan, hostAwayAt}: kept in storage (outlives the object)
    this.host = null;
    this.guest = null;
    this.n = 0; // the number of the latest guest
    this.acked = null; // the host has heard of guest n: its frames may go to it
    this.guestSeen = 0;
    this.quietSince = Date.now(); // no guest since then
  }

  async load() {
    if (this.rec === undefined) this.rec = (await this.ctx.storage.get("room")) ?? null;
    return this.rec;
  }

  async save(rec) {
    this.rec = rec;
    if (rec) await this.ctx.storage.put("room", rec);
    else await this.ctx.storage.deleteAll();
  }

  // The room, unless it has expired.
  async current() {
    const rec = await this.load();
    if (rec && rec.hostAwayAt !== null && Date.now() - rec.hostAwayAt > HOST_GRACE_MS) {
      await this.save(null);
      return null;
    }
    return rec;
  }

  guestFresh() {
    return this.guest !== null && Date.now() - this.guestSeen <= GUEST_STALE_MS;
  }

  async look(code) {
    const rec = await this.current();
    if (!rec) return { ok: false, why: "no_room" };
    if (!this.host) return { ok: false, why: "away" };
    if (this.guestFresh()) return { ok: false, why: "full" };
    return { ok: true, lan: rec.lan };
  }

  async armAlarm() {
    const rec = this.rec;
    const due = [];
    if (rec && rec.hostAwayAt !== null) due.push(rec.hostAwayAt + HOST_GRACE_MS + 50);
    if (rec && this.host && !this.guest) due.push(this.quietSince + ROOM_IDLE_MS);
    if (due.length) await this.ctx.storage.setAlarm(Math.min(...due));
    else await this.ctx.storage.deleteAlarm();
  }

  async alarm() {
    const rec = await this.current();
    if (rec && this.host && !this.guest && Date.now() - this.quietSince >= ROOM_IDLE_MS) {
      const host = this.host;
      this.host = null;
      send(host, { t: "error", why: "idle" });
      hangUp(host);
      await this.save(null);
    }
    await this.armAlarm();
  }

  accept(onMessage, onGone) {
    const [client, server] = Object.values(new WebSocketPair());
    server.accept();
    server.binaryType = "arraybuffer"; // (newer runtimes hand binary messages over as Blobs)
    server.addEventListener("message", (ev) => onMessage(server, ev.data));
    server.addEventListener("close", () => onGone(server));
    server.addEventListener("error", () => onGone(server));
    return [client, server];
  }

  async fetch(request) {
    const url = new URL(request.url);
    const code = url.searchParams.get("code");
    if (url.pathname === `${API}/look`) return json(await this.look(code));
    if (url.pathname === `${API}/join`) return this.join(code);
    if (url.searchParams.get("new") === "1") {
      if (await this.current()) return new Response("taken\n", { status: 409 });
      await this.save({ code, key: hex(16), lan: "", hostAwayAt: null });
    } else {
      const rec = await this.current();
      if (!rec || !sameText(rec.key, url.searchParams.get("key") ?? "")) return refuse("gone");
      const [oldHost, guest] = [this.host, this.guest];
      this.host = this.guest = null;
      hangUp(oldHost); // (a link of the host's that had not noticed it was dead) ...
      hangUp(guest, CLOSE_HOST_AWAY); // ... took the guest's channel with it
    }
    const [client, server] = this.accept(
      (ws, data) => this.fromHost(ws, data),
      (ws) => this.hostGone(ws),
    );
    this.host = server;
    this.acked = null;
    this.quietSince = Date.now();
    this.rec.hostAwayAt = null;
    await this.save(this.rec);
    send(server, { t: "room", code: this.rec.code, key: this.rec.key });
    await this.armAlarm();
    return new Response(null, { status: 101, webSocket: client });
  }

  async fromHost(ws, data) {
    if (ws !== this.host) return;
    if (typeof data !== "string") {
      if (data.byteLength > BINARY_MAX) return hangUp(ws, 1009);
      if (this.guest && this.acked === this.n) send(this.guest, data);
      return;
    }
    if (data.length > TEXT_MAX) return;
    let word;
    try {
      word = JSON.parse(data);
    } catch {
      return;
    }
    if (!word || typeof word !== "object") return;
    if (word.t === "lan" && typeof word.lan === "string") {
      this.rec.lan = word.lan.slice(0, LAN_MAX);
      await this.save(this.rec);
    } else if (word.t === "ack" && word.n === this.n && this.guest) {
      this.acked = this.n;
    } else if (word.t === "close") {
      const [host, guest] = [this.host, this.guest];
      this.host = this.guest = null;
      hangUp(guest, CLOSE_HOST_AWAY);
      hangUp(host);
      await this.save(null);
      await this.armAlarm();
    }
  }

  async hostGone(ws) {
    if (ws !== this.host) return;
    const guest = this.guest;
    this.host = this.guest = null;
    this.acked = null;
    hangUp(guest, CLOSE_HOST_AWAY); // the guest's game waits and comes back
    const rec = await this.load();
    if (rec) {
      rec.hostAwayAt = Date.now();
      await this.save(rec);
    }
    await this.armAlarm();
  }

  async join(code) {
    const answer = await this.look(code);
    if (!answer.ok) return refuse(answer.why);
    const [client, server] = this.accept(
      (ws, data) => this.fromGuest(ws, data),
      (ws) => this.guestGone(ws),
    );
    const old = this.guest;
    this.guest = server;
    hangUp(old); // (a guest that had gone silent)
    this.n += 1;
    this.acked = null;
    this.guestSeen = Date.now();
    send(this.host, { t: "peer", on: true, n: this.n });
    send(server, { t: "joined" });
    await this.armAlarm();
    return new Response(null, { status: 101, webSocket: client });
  }

  fromGuest(ws, data) {
    if (ws !== this.guest) return;
    this.guestSeen = Date.now();
    if (typeof data === "string") return;
    if (data.byteLength > BINARY_MAX) return hangUp(ws, 1009);
    if (this.host) send(this.host, data);
  }

  async guestGone(ws) {
    if (ws !== this.guest) return;
    this.guest = null;
    this.acked = null;
    this.quietSince = Date.now();
    send(this.host, { t: "peer", on: false });
    await this.armAlarm();
  }
}
