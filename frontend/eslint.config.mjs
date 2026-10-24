import { FlatCompat } from "@eslint/eslintrc";

const compat = new FlatCompat({ baseDirectory: import.meta.dirname });

export default [
  ...compat.extends("next/core-web-vitals", "next/typescript"),
  { rules: { "@typescript-eslint/no-explicit-any": "off", "react-hooks/exhaustive-deps": "off" } },
  {
    files: ["src/features/**/*.{ts,tsx}"],
    rules: {
      "no-restricted-imports": ["error", {
        patterns: [{
          group: ["@/app/**", "@/components/app-shell"],
          message: "Features must not depend on route files or the application composition shell.",
        }],
      }],
    },
  },
  {
    files: ["src/shared/**/*.{ts,tsx}", "src/lib/**/*.{ts,tsx}"],
    rules: {
      "no-restricted-imports": ["error", {
        patterns: [{
          group: ["@/features/**", "@/app/**", "@/components/**"],
          message: "Shared components and utilities must remain independent of features and app composition.",
        }],
      }],
    },
  },
];
