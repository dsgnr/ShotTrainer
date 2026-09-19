// Session categories. The strings are stored verbatim in the database and the
// controller validates them, so the page sends them back unchanged.
export const SESSION_CATEGORIES = ["practice", "sighter", "match"] as const;

export type SessionCategory = (typeof SESSION_CATEGORIES)[number];

export const DEFAULT_SESSION_CATEGORY: SessionCategory = "practice";

/** The display label for a category, such as `Practice`. */
export function categoryLabel(category: string): string {
  return category.length === 0 ? category : category[0]!.toUpperCase() + category.slice(1);
}
