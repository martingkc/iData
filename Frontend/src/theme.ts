export const themeOptions = [
  { id: "light", label: "Light" },
  { id: "dark", label: "Dark" }
] as const;

export type ThemeId = (typeof themeOptions)[number]["id"];
