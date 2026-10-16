/* Tiny DOM helpers shared by every module. */

/** The element with this id; fails loudly, since a missing id is a bug in index.html. */
export function $(id) {
  const node = document.getElementById(id);
  if (node === null) throw new Error(`expected an element with id "${id}" in index.html, found none`);
  return node;
}

/** Build a DOM element; children are strings (shown as text, never as HTML) or nodes. */
export function el(tag, props = {}, ...children) {
  const node = Object.assign(document.createElement(tag), props);
  node.append(...children);
  return node;
}

/** Resolve after `ms` milliseconds (used between polls). */
export function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
