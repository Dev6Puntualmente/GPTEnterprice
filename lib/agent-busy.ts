type Listener = () => void;

let busyRefs = 0;
const listeners = new Set<Listener>();

function notify() {
  for (const listener of listeners) {
    listener();
  }
}

/** Marca que el agente está trabajando (chat stream, tools, jobs). */
export function acquireAgentBusy(): () => void {
  busyRefs += 1;
  if (busyRefs === 1) {
    notify();
  }
  return () => {
    busyRefs = Math.max(0, busyRefs - 1);
    notify();
  };
}

export function isAgentBusy(): boolean {
  return busyRefs > 0;
}

export function subscribeAgentBusy(listener: Listener): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}
