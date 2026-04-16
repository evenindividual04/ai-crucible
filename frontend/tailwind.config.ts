import type { Config } from "tailwindcss";

const config: Config = {
    darkMode: "class",
    content: [
        "./pages/**/*.{js,ts,jsx,tsx,mdx}",
        "./components/**/*.{js,ts,jsx,tsx,mdx}",
        "./app/**/*.{js,ts,jsx,tsx,mdx}",
    ],
    theme: {
        extend: {
            // Theme is now defined in globals.css using @theme directive (Tailwind v4)
            // Keeping minimal config for compatibility
            colors: {
                // Map CSS variables to Tailwind utilities
                primary: "var(--color-primary)",
                "primary-hover": "var(--color-primary-hover)",
                background: "var(--color-background)",
                "background-elevated": "var(--color-background-elevated)",
                surface: "var(--color-surface)",
                "surface-hover": "var(--color-surface-hover)",
                border: "var(--color-border)",
                "border-hover": "var(--color-border-hover)",
                text: "var(--color-text)",
                "text-muted": "var(--color-text-muted)",
                "text-dim": "var(--color-text-dim)",

                // Severity levels
                critical: "var(--color-critical)",
                high: "var(--color-high)",
                medium: "var(--color-medium)",
                low: "var(--color-low)",
                secure: "var(--color-secure)",

                // Status colors
                success: "var(--color-success)",
                warning: "var(--color-warning)",
                error: "var(--color-error)",
                info: "var(--color-info)",
            },
            fontFamily: {
                sans: "var(--font-sans)",
                mono: "var(--font-mono)",
            },
        },
    },
    plugins: [require("tailwindcss-animate")],
};

export default config;
