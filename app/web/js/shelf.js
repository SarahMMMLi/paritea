// The page's copy of the shelf: the diagrams made in this session. The engine holds the diagrams themselves; this
// keeps what the page needs to list them (id, name, size) and tells pages when the list changes.

class Shelf extends EventTarget {
  constructor() {
    super();
    this.entries = new Map();
  }

  add(entry) {
    const { id, name, summary, source } = entry;
    const isNew = !this.entries.has(id);
    this.entries.set(id, { id, name, summary, source });
    if (isNew) this.dispatchEvent(new Event("change"));
  }

  remove(id) {
    if (this.entries.delete(id)) this.dispatchEvent(new Event("change"));
  }

  clear() {
    this.entries.clear();
    this.dispatchEvent(new Event("change"));
  }

  list() {
    return [...this.entries.values()];
  }

  get size() {
    return this.entries.size;
  }
}

export const shelf = new Shelf();
