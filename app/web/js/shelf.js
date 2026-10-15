// The page's copy of the shelf: the diagrams and noise models made in this session. The engine holds the objects; this
// keeps what the page needs to list them (id, name, size) and tells pages when the list changes.

class Shelf extends EventTarget {
  constructor() {
    super();
    this.entries = new Map();
    this.noise = new Map();
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

  addNoise(noise) {
    const { id, name, summary, diagram } = noise;
    const isNew = !this.noise.has(id);
    this.noise.set(id, { id, name, summary, diagram });
    if (isNew) this.dispatchEvent(new Event("change"));
  }

  removeNoise(id) {
    if (this.noise.delete(id)) this.dispatchEvent(new Event("change"));
  }

  clear() {
    this.entries.clear();
    this.noise.clear();
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
