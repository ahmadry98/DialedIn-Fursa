import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "DialedIN Espresso Shot Review",
    short_name: "DialedIN",
    description: "Guided espresso shot timing and grind recommendations.",
    start_url: "/",
    scope: "/",
    display: "standalone",
    background_color: "#f5f6f2",
    theme_color: "#2f6f4f",
    orientation: "portrait",
    categories: ["food", "productivity", "utilities"],
    icons: [
      {
        src: "/icon.svg",
        sizes: "any",
        type: "image/svg+xml",
        purpose: "any",
      },
      {
        src: "/icon.svg",
        sizes: "any",
        type: "image/svg+xml",
        purpose: "maskable",
      },
    ],
  };
}
