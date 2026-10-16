/* The one "current step" of an answer card, shared by the route view and the step list in Details,
   so selecting a step in either moves the other. */

/** A step selection starting at `initial` (0-based index into the route's steps). */
export function createStepSync(initial) {
  let current = initial;
  const listeners = [];
  return {
    get current() { return current; },
    /** Make step `index` the current one and tell every listener. */
    select(index) {
      current = index;
      for (const listener of listeners) listener(index);
    },
    /** Call `listener(index)` after every selection. */
    onChange(listener) { listeners.push(listener); },
  };
}
