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
const LOG_MAX = 200; // lines of the log kept (the newest)
const DAILY_LIMIT = 100_000; // requests a day of a free Durable Object (a frame message is 1/20)
const HEALTH_LIMIT_PCT = 90; // /v1/health says "near_limit" (HTTP 503) from here
const FRAMES_PER_REQUEST = 20;
const RTT_MAX_MS = 60_000;
const FLUSH_MS = 5 * 60_000; // a room with new frames tells the Hub at least this often

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

const json = (body, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });

const today = () => new Date().toISOString().slice(0, 10); // (the day of the free share: UTC)
const usedPct = (t) =>
  Math.round((10_000 * (Math.ceil(t.frames / FRAMES_PER_REQUEST) + t.events)) / DAILY_LIMIT) / 100;

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
    const hub = () => env.HUB.get(env.HUB.idFromName("hub"), { locationHint: "apac" });
    if (url.pathname === `${API}/health`) return hub().fetch("https://hub/health");
    if (url.pathname === `${API}/status`) {
      const given = url.searchParams.get("key") ?? "";
      if (!env.ADMIN_KEY || !sameText(given, env.ADMIN_KEY)) {
        return new Response("no\n", { status: 403 });
      }
      const asked = url.searchParams.get("log") ?? "";
      return hub().fetch(`https://hub/status?log=${/^\d+$/.test(asked) ? asked : "20"}`);
    }
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
    this.env = env;
    this.rec = undefined; // {code, key, lan, hostAwayAt}: kept in storage (outlives the object)
    this.host = null;
    this.guest = null;
    this.n = 0; // the number of the latest guest
    this.acked = null; // the host has heard of guest n: its frames may go to it
    this.guestSeen = 0;
    this.quietSince = Date.now(); // no guest since then
    this.frames = 0; // frames passed on since this object started ...
    this.told = 0; // ... and how many of them the Hub has been told of
    this.flushAt = null; // the Hub must hear of the new frames by then
    this.rtt = null; // the host's word on the ping between the players
  }

  // Tell the Hub (the relay's book: who is there, the log, the day's numbers). Never in the way:
  // if the Hub cannot be reached the room goes on.
  report(ev, why) {
    const body = { ev, code: this.rec?.code, frames: this.frames - this.told };
    if (why) body.why = why;
    this.told = this.frames;
    this.flushAt = null;
    const hub = this.env.HUB.get(this.env.HUB.idFromName("hub"), { locationHint: "apac" });
    this.ctx.waitUntil(
      hub
        .fetch("https://hub/event", { method: "POST", body: JSON.stringify(body) })
        .then((r) => r.text())
        .catch(() => {}),
    );
  }

  countFrame() {
    this.frames += 1;
    if (this.flushAt === null) {
      this.flushAt = Date.now() + FLUSH_MS;
      this.armAlarm().catch(() => {});
    }
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
      this.report("room_end", "expired");
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

  // What the Hub shows of this room, or null when it is gone.
  async info() {
    if (!(await this.current())) return null;
    const state = !this.host ? "host_away" : this.guest ? "playing" : "waiting";
    return { state, rtt_ms: this.guest ? this.rtt : null };
  }

  async armAlarm() {
    const rec = this.rec;
    const due = [];
    if (rec && rec.hostAwayAt !== null) due.push(rec.hostAwayAt + HOST_GRACE_MS + 50);
    if (rec && this.host && !this.guest) due.push(this.quietSince + ROOM_IDLE_MS);
    if (rec && this.flushAt !== null) due.push(this.flushAt);
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
      this.report("room_end", "idle");
      await this.save(null);
    } else if (rec && this.flushAt !== null && Date.now() >= this.flushAt) {
      this.report("flush");
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
    if (url.pathname === `${API}/_info`) return json(await this.info()); // (the Hub asks)
    let back = false;
    if (url.searchParams.get("new") === "1") {
      if (await this.current()) return new Response("taken\n", { status: 409 });
      await this.save({ code, key: hex(16), lan: "", hostAwayAt: null });
    } else {
      back = true;
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
    this.rtt = null;
    this.quietSince = Date.now();
    this.rec.hostAwayAt = null;
    await this.save(this.rec);
    this.report(back ? "host_back" : "room_new");
    send(server, { t: "room", code: this.rec.code, key: this.rec.key });
    await this.armAlarm();
    return new Response(null, { status: 101, webSocket: client });
  }

  async fromHost(ws, data) {
    if (ws !== this.host) return;
    if (typeof data !== "string") {
      if (data.byteLength > BINARY_MAX) return hangUp(ws, 1009);
      this.countFrame();
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
    } else if (word.t === "stat") {
      if (typeof word.rtt === "number" && word.rtt >= 0 && word.rtt <= RTT_MAX_MS && this.guest) {
        this.rtt = Math.trunc(word.rtt);
      }
    } else if (word.t === "close") {
      const [host, guest] = [this.host, this.guest];
      this.host = this.guest = null;
      hangUp(guest, CLOSE_HOST_AWAY);
      hangUp(host);
      this.report("room_end", "host_closed");
      await this.save(null);
      await this.armAlarm();
    }
  }

  async hostGone(ws) {
    if (ws !== this.host) return;
    const guest = this.guest;
    this.host = this.guest = null;
    this.acked = null;
    this.rtt = null;
    hangUp(guest, CLOSE_HOST_AWAY); // the guest's game waits and comes back
    const rec = await this.load();
    if (rec) {
      rec.hostAwayAt = Date.now();
      await this.save(rec);
      this.report("host_out", "host_link");
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
    if (old) this.report("guest_replaced");
    this.report("guest_in");
    this.n += 1;
    this.rtt = null;
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
    this.countFrame();
    if (this.host) send(this.host, data);
  }

  async guestGone(ws) {
    if (ws !== this.guest) return;
    this.guest = null;
    this.acked = null;
    this.rtt = null;
    this.quietSince = Date.now();
    this.report("guest_out", "guest_link");
    send(this.host, { t: "peer", on: false });
    await this.armAlarm();
  }
}

// The relay's book (one object, always the same name): which rooms are alive, the log with its
// reasons, and the day's numbers. Rooms report to it when something happens, never frame by frame.
export class Hub {
  constructor(ctx, env) {
    this.ctx = ctx;
    this.env = env;
    this.book = undefined;
  }

  async load() {
    if (this.book === undefined) {
      this.book = (await this.ctx.storage.get("book")) ?? {
        day: "",
        today: null,
        rooms: {},
        log: [],
      };
    }
    const day = today();
    if (this.book.day !== day) {
      this.book.day = day;
      this.book.today = { rooms: 0, joins: 0, frames: 0, events: 0 };
    }
    return this.book;
  }

  async event(report) {
    const book = await this.load();
    const { ev, code, why, frames } = report;
    book.today.events += 1;
    if (Number.isInteger(frames) && frames > 0) book.today.frames += frames;
    if (ev !== "flush") {
      const line = { at: Date.now(), ev, code };
      if (why) line.why = why;
      book.log.push(line);
      if (book.log.length > LOG_MAX) book.log.splice(0, book.log.length - LOG_MAX);
    }
    if (ev === "room_new") {
      book.today.rooms += 1;
      book.rooms[code] = Date.now();
    } else if (ev === "guest_in") {
      book.today.joins += 1;
    } else if (ev === "room_end") {
      delete book.rooms[code];
    }
    await this.ctx.storage.put("book", book);
  }

  async fetch(request) {
    const url = new URL(request.url);
    if (url.pathname === "/event") {
      await this.event(await request.json());
      return new Response("ok\n");
    }
    const book = await this.load();
    const pct = usedPct(book.today);
    if (url.pathname === "/health") {
      const ok = pct < HEALTH_LIMIT_PCT;
      const body = { ok, rooms: Object.keys(book.rooms).length, used_pct: pct };
      if (!ok) body.why = "near_limit";
      return json(body, ok ? 200 : 503);
    }
    const lines = Number(url.searchParams.get("log") ?? 20);
    const now = Date.now();
    const asked = await Promise.all(
      Object.entries(book.rooms).map(async ([code, born]) => {
        const stub = this.env.ROOMS.get(this.env.ROOMS.idFromName(code), { locationHint: "apac" });
        try {
          const info = await (await stub.fetch(`https://room${API}/_info?code=${code}`)).json();
          return { code, born, info };
        } catch {
          return { code, born, info: null };
        }
      }),
    );
    let changed = false;
    const rooms = [];
    for (const { code, born, info } of asked) {
      if (!info) {
        delete book.rooms[code]; // (a room that is gone and never said so)
        changed = true;
        continue;
      }
      const age_s = Math.floor((now - born) / 1000);
      rooms.push({ code, state: info.state, age_s, rtt_ms: info.rtt_ms });
    }
    if (changed) await this.ctx.storage.put("book", book);
    return json({
      day: book.day,
      rooms,
      today: { ...book.today, used_pct: pct },
      log: lines > 0 ? book.log.slice(-lines) : [],
    });
  }
}
