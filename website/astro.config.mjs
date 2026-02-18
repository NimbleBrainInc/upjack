import { defineConfig } from "astro/config";
import starlight from "@astrojs/starlight";
import sitemap from "@astrojs/sitemap";

export default defineConfig({
  site: "https://upjack.dev",
  integrations: [
    starlight({
      title: "Upjack",
      description:
        "Build AI-powered apps by describing your domain — not writing code.",
      head: [
        {
          tag: "script",
          content: `(function(w,d,s,l,i){w[l]=w[l]||[];w[l].push({'gtm.start':
new Date().getTime(),event:'gtm.js'});var f=d.getElementsByTagName(s)[0],
j=d.createElement(s),dl=l!='dataLayer'?'&l='+l:'';j.async=true;j.src=
'https://www.googletagmanager.com/gtm.js?id='+i+dl;f.parentNode.insertBefore(j,f);
})(window,document,'script','dataLayer','GTM-W9BSLGCG');`,
        },
        {
          tag: "meta",
          attrs: {
            property: "og:image",
            content: "https://upjack.dev/og-image.png",
          },
        },
        {
          tag: "meta",
          attrs: {
            property: "og:image:width",
            content: "1200",
          },
        },
        {
          tag: "meta",
          attrs: {
            property: "og:image:height",
            content: "630",
          },
        },
      ],
      components: {
        ThemeProvider: "./src/components/ThemeProvider.astro",
      },
      logo: {
        light: "./src/assets/logo-light.svg",
        dark: "./src/assets/logo-dark.svg",
        replacesTitle: false,
      },
      social: [
        {
          icon: "github",
          label: "GitHub",
          href: "https://github.com/NimbleBrainInc/upjack",
        },
      ],
      customCss: ["./src/styles/custom.css"],
      sidebar: [
        {
          label: "Getting Started",
          items: [
            { label: "Introduction", slug: "introduction" },
            { label: "Quick Start", slug: "quick-start" },
          ],
        },
        {
          label: "Tutorials",
          items: [
            {
              label: "Build a Todo App",
              slug: "tutorials/todo-app",
            },
          ],
        },
        {
          label: "Concepts",
          items: [
            { label: "Architecture", slug: "concepts/architecture" },
            { label: "Thesis", slug: "concepts/thesis" },
            { label: "Three Tiers", slug: "concepts/three-tiers" },
          ],
        },
        {
          label: "Reference",
          items: [
            { label: "Manifest", slug: "reference/manifest" },
            { label: "Schemas", slug: "reference/schemas" },
            { label: "Entity Model", slug: "reference/entity-model" },
            { label: "Runtime Tools", slug: "reference/runtime-tools" },
            {
              label: "Bundles & Skills",
              slug: "reference/bundles-and-skills",
            },
            { label: "Lifecycle", slug: "reference/lifecycle" },
          ],
        },
        {
          label: "Libraries",
          items: [
            { label: "Python", slug: "libraries/python" },
            { label: "TypeScript", slug: "libraries/typescript" },
          ],
        },
        {
          label: "Examples",
          items: [
            { label: "Overview", slug: "examples/overview" },
            { label: "CRM", slug: "examples/crm" },
            { label: "Todo", slug: "examples/todo" },
            {
              label: "Research Assistant",
              slug: "examples/research-assistant",
            },
          ],
        },
      ],
    }),
    sitemap(),
  ],
});
