import { BarChart3, Bot, ClipboardList, FolderKanban, Settings2, UploadCloud } from "lucide-react";

export const navLinks = [
  { to: "/", icon: BarChart3, key: "nav.dashboard" },
  { to: "/groups", icon: FolderKanban, key: "nav.groups" },
  { to: "/submissions", icon: UploadCloud, key: "nav.submissions" },
  { to: "/evaluations", icon: ClipboardList, key: "nav.evaluations" },
  { to: "/providers", icon: Bot, key: "nav.providers" },
  { to: "/settings", icon: Settings2, key: "nav.settings" },
];
