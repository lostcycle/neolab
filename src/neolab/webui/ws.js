// Auto-reconnecting WebSocket wrapper.
// Holds a single live socket; `send(obj)` JSON-encodes and writes;
// closes trigger a 1s reconnect.

export class WS {
  constructor(url, { onOpen, onMessage, onClose } = {}) {
    this.url = url;
    this.handlers = { onOpen, onMessage, onClose };
    this._connect();
  }

  _connect() {
    this.sock = new WebSocket(this.url);
    this.sock.onopen = () => this.handlers.onOpen?.();
    this.sock.onmessage = (e) => {
      try {
        this.handlers.onMessage?.(JSON.parse(e.data));
      } catch (err) {
        console.error("neolab ws: bad JSON", err, e.data);
      }
    };
    this.sock.onclose = () => {
      this.handlers.onClose?.();
      setTimeout(() => this._connect(), 1000);
    };
    this.sock.onerror = (e) => console.warn("neolab ws error", e);
  }

  send(obj) {
    if (this.sock.readyState === WebSocket.OPEN) {
      this.sock.send(JSON.stringify(obj));
    }
  }
}
