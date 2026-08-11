import { WS_URL } from './config.js';

const INITIAL_RETRY_MS = 1000;
const MAX_RETRY_MS = 30000;
const RETRY_BACKOFF = 2;

export class JarvisSocket {
  constructor(url = WS_URL) {
    this.url = url;
    this.ws = null;
    this.intentionallyClosed = false;
    this.retryDelay = INITIAL_RETRY_MS;
    this.retryTimer = null;

    this.onopen = null;
    this.onmessage = null;
    this.onclose = null;
    this.onerror = null;
  }

  connect() {
    if (this.ws) return;
    this.intentionallyClosed = false;

    try {
      this.ws = new WebSocket(this.url);
    } catch (err) {
      this._handleError(err);
      this._scheduleReconnect();
      return;
    }

    this.ws.onopen = () => {
      this.retryDelay = INITIAL_RETRY_MS;
      if (this.onopen) this.onopen();
    };

    this.ws.onmessage = (event) => {
      if (this.onmessage) this.onmessage(event.data);
    };

    this.ws.onerror = (event) => {
      if (this.onerror) this.onerror(event);
    };

    this.ws.onclose = () => {
      this.ws = null;
      if (this.onclose) this.onclose();
      if (!this.intentionallyClosed) {
        this._scheduleReconnect();
      }
    };
  }

  send(data) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(data);
    }
  }

  close() {
    this.intentionallyClosed = true;
    if (this.retryTimer) {
      clearTimeout(this.retryTimer);
      this.retryTimer = null;
    }
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }

  _handleError(error) {
    if (this.onerror) this.onerror(error);
  }

  _scheduleReconnect() {
    if (this.retryTimer) return;
    this.retryTimer = setTimeout(() => {
      this.retryTimer = null;
      this.connect();
    }, this.retryDelay);
    this.retryDelay = Math.min(this.retryDelay * RETRY_BACKOFF, MAX_RETRY_MS);
  }
}
