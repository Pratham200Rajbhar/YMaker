import next from "eslint-config-next";
import nextCoreWebVitals from "eslint-config-next/core-web-vitals";
import nextTypescript from "eslint-config-next/typescript";

const addReactVersion = (configs) =>
  configs.map((config) => ({
    ...config,
    settings: {
      ...config.settings,
      react: {
        ...(config.settings?.react || {}),
        version: "19.2.6",
      },
    },
  }));

const eslintConfig = [
  ...addReactVersion(next),
  ...addReactVersion(nextCoreWebVitals),
  ...addReactVersion(nextTypescript),
  {
    files: ["**/*.js", "**/*.jsx", "**/*.ts", "**/*.tsx"],
    rules: {
      "no-unused-vars": ["warn", { "argsIgnorePattern": "^_", "varsIgnorePattern": "^_", "caughtErrorsIgnorePattern": "^_" }],
      "@typescript-eslint/no-unused-vars": ["warn", { "argsIgnorePattern": "^_", "varsIgnorePattern": "^_", "caughtErrorsIgnorePattern": "^_" }]
    },
  },
  {
    ignores: ["node_modules/**", ".next/**", "out/**", "build/**", "next-env.d.ts"],
  },
];

export default eslintConfig;
