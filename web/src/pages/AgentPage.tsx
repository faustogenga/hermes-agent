import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import {
  Compass,
  Plane,
  Plus,
  Rocket,
  Search,
  Settings,
  Shield,
  Sparkles,
  SquareTerminal,
  Target,
  Trash2,
} from "lucide-react";
import { api } from "@/lib/api";
import type { AgentPresetDetail, AgentProfileResponse, CronJob, PluginManifestResponse } from "@/lib/api";
import { formatTokenCount } from "@/lib/format";
import { cn } from "@/lib/utils";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectOption } from "@/components/ui/select";

type EditorState = {
  name: string;
  slug: string;
  emoji: string;
  role: string;
  goal: string;
  description: string;
  personality: string;
  default_skills: string;
  soul_content: string;
  agents_content: string;
};

type PresetTheme = {
  label: string;
  mood: string;
  stageClass: string;
  avatarClass: string;
  glowClass: string;
  trailClass: string;
  cardClass: string;
  hoverClass: string;
  selectedClass: string;
  activeClass: string;
};

const textareaClass = "min-h-[140px] w-full border border-border bg-background/40 px-3 py-2 font-courier text-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-foreground/30 focus-visible:border-foreground/25";
const EMOJI_GROUPS = [
  {
    label: "Core",
    emojis: ["🤖", "✨", "🧠", "⚡", "🛠️", "🧭", "🚀", "🛰️", "🔮", "💡"],
  },
  {
    label: "Work",
    emojis: ["🎯", "📈", "🧪", "📦", "📝", "🔍", "🗂️", "📡", "💼", "🧬"],
  },
  {
    label: "Travel",
    emojis: ["✈️", "🌍", "🗺️", "🏝️", "🧳", "🚆", "🚗", "⛵", "🏔️", "🌆"],
  },
  {
    label: "Style",
    emojis: ["🔥", "🌙", "🌟", "🎨", "🪩", "💎", "🌊", "🍀", "🦾", "🎵"],
  },
];
const ALL_PICKER_EMOJIS = Array.from(new Set(EMOJI_GROUPS.flatMap((group) => group.emojis)));

function presetToEditor(preset: AgentPresetDetail): EditorState {
  return {
    name: preset.name || "",
    slug: preset.slug || "",
    emoji: preset.emoji || "🤖",
    role: preset.role || "",
    goal: preset.goal || "",
    description: preset.description || "",
    personality: preset.personality || "",
    default_skills: (preset.default_skills || []).join(", "),
    soul_content: preset.soul_content || "",
    agents_content: preset.agents_content || "",
  };
}

function buildTemplate(template: "default" | "lead-hunter" | "flight-finder" | "blank"): EditorState {
  if (template === "blank") {
    return {
      name: "",
      slug: "",
      emoji: "🤖",
      role: "",
      goal: "",
      description: "",
      personality: "",
      default_skills: "",
      soul_content: "",
      agents_content: "",
    };
  }
  if (template === "lead-hunter") {
    return {
      name: "Lead Hunter",
      slug: "lead-hunter",
      emoji: "🎯",
      role: "Evidence-first local SMB opportunity finder",
      goal: "Find outreach-ready local businesses with weak digital demand capture",
      description: "Commercial prospecting preset for website, app, and local SEO leads.",
      personality: "",
      default_skills: "local-business-opportunity-finder, hermes-lead-hunter-setup",
      soul_content: "You are Hermes Lead Hunter, a skeptical, evidence-first local SMB opportunity finder for a web and app development agency.",
      agents_content: "Verify the business, inspect the website and socials directly, and only include leads with clear digital upside.",
    };
  }
  if (template === "flight-finder") {
    return {
      name: "Flight Finder",
      slug: "flight-finder",
      emoji: "✈️",
      role: "Evidence-first airfare tracker and deal watcher",
      goal: "Monitor specific routes, surface the best grounded fare options, and keep a clean historical record for comparison over time",
      description: "Flight-monitoring preset optimized for Google Flights first, corroborated backup checks, and structured Airtable tracking.",
      personality: "flight-finder",
      default_skills: "flight-fare-monitoring",
      soul_content: "You are Hermes Flight Finder, a specialized airfare-monitoring preset that tracks specific routes with grounded evidence and stores the best fare options over time.",
      agents_content: "Use Google Flights first, corroborate with backup aggregators, and persist the top grounded exact-date fare options for each monitored route.",
    };
  }
  return {
    name: "New Agent",
    slug: "new-agent",
    emoji: "🤖",
    role: "Specialized Hermes preset",
    goal: "Handle a focused workflow with shared keys and runtime",
    description: "Lightweight preset inside the current Hermes profile.",
    personality: "",
    default_skills: "",
    soul_content: "You are a specialized Hermes preset.",
    agents_content: "",
  };
}

function getPresetTheme(preset: Pick<AgentPresetDetail, "slug" | "name" | "description">): PresetTheme {
  const slug = preset.slug.toLowerCase();
  const text = `${preset.name} ${preset.description}`.toLowerCase();

  if (slug === "default") {
    return {
      label: "Default",
      mood: "General-purpose assistant",
      stageClass: "from-emerald-300/[0.08] via-emerald-200/[0.02] to-transparent",
      avatarClass: "border-emerald-200/10 bg-white/[0.04] text-[#e6eaf0]",
      glowClass: "shadow-[0_10px_28px_rgba(0,0,0,0.18)]",
      trailClass: "bg-[#4F8CFF]/60",
      cardClass: "border-emerald-200/10 bg-[#0b1a18]",
      hoverClass: "hover:border-emerald-200/20",
      selectedClass: "border-emerald-300/30",
      activeClass: "border-emerald-300/20",
    };
  }

  if (slug.includes("lead") || text.includes("lead hunter") || text.includes("prospect")) {
    return {
      label: "Lead Hunter",
      mood: "Investigator mode · search-first",
      stageClass: "from-amber-300/[0.08] via-amber-200/[0.02] to-transparent",
      avatarClass: "border-amber-200/10 bg-white/[0.04] text-[#e6eaf0]",
      glowClass: "shadow-[0_10px_28px_rgba(0,0,0,0.18)]",
      trailClass: "bg-[#4F8CFF]/60",
      cardClass: "border-amber-200/10 bg-[#1a1710]",
      hoverClass: "hover:border-amber-200/20",
      selectedClass: "border-amber-300/30",
      activeClass: "border-amber-300/20",
    };
  }

  if (slug.includes("housing") || slug.includes("rent") || text.includes("apartment") || text.includes("rental-search")) {
    return {
      label: "Housing Hunter",
      mood: "Rental watcher mode · shortlist first",
      stageClass: "from-teal-300/[0.08] via-emerald-200/[0.02] to-transparent",
      avatarClass: "border-teal-200/10 bg-white/[0.04] text-[#e6eaf0]",
      glowClass: "shadow-[0_10px_28px_rgba(0,0,0,0.18)]",
      trailClass: "bg-[#4F8CFF]/60",
      cardClass: "border-teal-200/10 bg-[#0f1a1a]",
      hoverClass: "hover:border-teal-200/20",
      selectedClass: "border-teal-300/30",
      activeClass: "border-teal-300/20",
    };
  }

  if (slug.includes("flight") || text.includes("airfare") || text.includes("flight-monitoring")) {
    return {
      label: "Flight Finder",
      mood: "Route tracker mode · price watch",
      stageClass: "from-sky-300/[0.08] via-sky-200/[0.02] to-transparent",
      avatarClass: "border-sky-200/10 bg-white/[0.04] text-[#e6eaf0]",
      glowClass: "shadow-[0_10px_28px_rgba(0,0,0,0.18)]",
      trailClass: "bg-[#4F8CFF]/60",
      cardClass: "border-sky-200/10 bg-[#10171f]",
      hoverClass: "hover:border-sky-200/20",
      selectedClass: "border-sky-300/30",
      activeClass: "border-sky-300/20",
    };
  }

  return {
    label: "Custom Persona",
    mood: "Specialized task mode",
    stageClass: "from-emerald-300/[0.08] via-emerald-200/[0.02] to-transparent",
    avatarClass: "border-emerald-200/10 bg-white/[0.04] text-[#e6eaf0]",
    glowClass: "shadow-[0_10px_28px_rgba(0,0,0,0.18)]",
    trailClass: "bg-[#4F8CFF]/60",
    cardClass: "border-emerald-200/10 bg-[#0b1a18]",
    hoverClass: "hover:border-emerald-200/20",
    selectedClass: "border-emerald-300/30",
    activeClass: "border-emerald-300/20",
  };
}

function summarizePreset(preset: AgentPresetDetail): string {
  return preset.description || preset.goal || preset.role || "No description yet.";
}

function getPresetModeLabel(preset: Pick<AgentPresetDetail, "slug" | "name" | "description">): string {
  const slug = preset.slug.toLowerCase();
  const text = `${preset.name} ${preset.description}`.toLowerCase();
  if (slug === "default") return "General";
  if (slug.includes("housing") || text.includes("apartment") || text.includes("rental")) return "Housing";
  if (slug.includes("flight") || text.includes("airfare") || text.includes("flight")) return "Tracker";
  if (slug.includes("lead") || text.includes("prospect") || text.includes("lead hunter")) return "Search";
  return "Custom";
}

function getPresetIcon(preset: Pick<AgentPresetDetail, "slug" | "name" | "description">) {
  const slug = preset.slug.toLowerCase();
  const text = `${preset.name} ${preset.description}`.toLowerCase();
  if (slug === "default") return Sparkles;
  if (slug.includes("housing") || text.includes("apartment") || text.includes("rental")) return Rocket;
  if (slug.includes("flight") || text.includes("airfare") || text.includes("flight")) return Plane;
  if (slug.includes("lead") || text.includes("prospect") || text.includes("lead hunter")) return Target;
  return Shield;
}

function renderPresetAvatar(
  preset: Pick<AgentPresetDetail, "slug" | "name" | "description" | "emoji">,
  className: string,
  fallbackClassName = "h-6 w-6",
) {
  if (preset.emoji) {
    return (
      <span className={cn("agent-avatar-core inline-flex h-full w-full items-center justify-center text-center leading-none", className)}>
        <span className="translate-y-[-0.5px]">{preset.emoji}</span>
      </span>
    );
  }
  const Icon = getPresetIcon(preset);
  return <Icon className={cn("agent-avatar-core", fallbackClassName)} />;
}

function renderPresetCardAvatar(
  preset: Pick<AgentPresetDetail, "slug" | "name" | "description" | "emoji">,
  sizeClass = "h-4 w-4",
) {
  return renderPresetAvatar(preset, "text-[0.86rem]", sizeClass);
}

export default function AgentPage() {
  const [profile, setProfile] = useState<AgentProfileResponse | null>(null);
  const [agentPlugins, setAgentPlugins] = useState<PluginManifestResponse[]>([]);
  const [cronJobs, setCronJobs] = useState<CronJob[]>([]);
  const [selectedSlug, setSelectedSlug] = useState<string>("");
  const [editor, setEditor] = useState<EditorState>(buildTemplate("blank"));
  const [status, setStatus] = useState<string>("");
  const [saving, setSaving] = useState(false);
  const [loadError, setLoadError] = useState<string>("");
  const [emojiPickerOpen, setEmojiPickerOpen] = useState(false);
  const [emojiSearch, setEmojiSearch] = useState("");
  const gridRef = useRef<HTMLDivElement | null>(null);
  const editorRef = useRef<HTMLDivElement | null>(null);
  const emojiPickerRef = useRef<HTMLDivElement | null>(null);
  const cardRefs = useRef<Record<string, HTMLDivElement | null>>({});
  const [mascotPosition, setMascotPosition] = useState({ x: 24, y: 24, ready: false });

  const load = async (preferredSlug?: string) => {
    const [next, plugins, jobs] = await Promise.all([
      api.getAgentProfile(),
      api.getPlugins().catch(() => []),
      api.getCronJobs().catch(() => []),
    ]);
    if (!next.current_preset || !Array.isArray(next.presets)) {
      throw new Error("Agent profile payload is missing preset data. Restart the dashboard so backend and frontend are on the same version.");
    }
    setLoadError("");
    setProfile(next);
    setAgentPlugins(plugins.filter((plugin) => Boolean(plugin.agentPage)));
    setCronJobs(jobs);
    const slug = preferredSlug || next.current_preset.slug;
    const selected = next.presets.find((preset) => preset.slug === slug) || next.current_preset;
    setSelectedSlug(selected.slug);
    setEditor(presetToEditor(selected));
  };

  useEffect(() => {
    load().catch((error) => {
      setProfile(null);
      setLoadError(error instanceof Error ? error.message : "Could not load agent presets.");
    });
  }, []);

  useEffect(() => {
    if (!emojiPickerOpen) return;
    const handlePointerDown = (event: MouseEvent) => {
      if (!emojiPickerRef.current?.contains(event.target as Node)) {
        setEmojiPickerOpen(false);
      }
    };
    document.addEventListener("mousedown", handlePointerDown);
    return () => document.removeEventListener("mousedown", handlePointerDown);
  }, [emojiPickerOpen]);

  const selectedPreset = useMemo(() => {
    if (!profile) return null;
    return profile.presets.find((preset) => preset.slug === selectedSlug) || profile.current_preset;
  }, [profile, selectedSlug]);

  const previewPreset = useMemo<AgentPresetDetail | null>(() => {
    if (!selectedPreset) return null;
    return {
      ...selectedPreset,
      name: editor.name || selectedPreset.name,
      slug: editor.slug || selectedPreset.slug,
      emoji: editor.emoji || selectedPreset.emoji,
      role: editor.role || selectedPreset.role,
      goal: editor.goal || selectedPreset.goal,
      description: editor.description || selectedPreset.description,
      personality: editor.personality || selectedPreset.personality,
      default_skills: editor.default_skills.split(",").map((item) => item.trim()).filter(Boolean),
      soul_content: editor.soul_content || selectedPreset.soul_content,
      agents_content: editor.agents_content || selectedPreset.agents_content,
    };
  }, [editor, selectedPreset]);

  const activeTheme = useMemo(() => {
    if (!profile) return null;
    return getPresetTheme(profile.current_preset);
  }, [profile]);

  const filteredPickerEmojis = useMemo(() => {
    const query = emojiSearch.trim().toLowerCase();
    if (!query) return ALL_PICKER_EMOJIS;
    return ALL_PICKER_EMOJIS.filter((emoji) => `${emoji}`.includes(query));
  }, [emojiSearch]);

  const buildPayload = () => ({
    name: editor.name.trim(),
    slug: editor.slug.trim() || undefined,
    emoji: editor.emoji.trim() || "🤖",
    role: editor.role.trim(),
    goal: editor.goal.trim(),
    description: editor.description.trim(),
    personality: editor.personality.trim(),
    default_skills: editor.default_skills.split(",").map((item) => item.trim()).filter(Boolean),
    soul_content: editor.soul_content,
    agents_content: editor.agents_content,
  });

  const pluginPagesBySlug = useMemo(() => {
    return agentPlugins.reduce<Record<string, PluginManifestResponse[]>>((acc, plugin) => {
      const slug = plugin.agentPage?.slug;
      if (!slug) return acc;
      if (!acc[slug]) acc[slug] = [];
      acc[slug].push(plugin);
      return acc;
    }, {});
  }, [agentPlugins]);

  const cronCountByAgent = useMemo(() => {
    return cronJobs.reduce<Record<string, number>>((acc, job) => {
      const key = job.agent_name || "default";
      acc[key] = (acc[key] || 0) + 1;
      return acc;
    }, {});
  }, [cronJobs]);

  const normalizedEditor = useMemo(() => JSON.stringify(buildPayload()), [editor]);
  const normalizedSelectedPreset = useMemo(() => {
    if (!selectedPreset) return "";
    return JSON.stringify({
      name: selectedPreset.name || "",
      slug: selectedPreset.slug || undefined,
      emoji: selectedPreset.emoji || "🤖",
      role: selectedPreset.role || "",
      goal: selectedPreset.goal || "",
      description: selectedPreset.description || "",
      personality: selectedPreset.personality || "",
      default_skills: selectedPreset.default_skills || [],
      soul_content: selectedPreset.soul_content || "",
      agents_content: selectedPreset.agents_content || "",
    });
  }, [selectedPreset]);
  const isDirty = Boolean(selectedPreset) && normalizedEditor !== normalizedSelectedPreset;

  useLayoutEffect(() => {
    if (!profile) return;

    const updatePosition = () => {
      const container = gridRef.current;
      const activeCard = cardRefs.current[profile.active_preset];
      if (!container || !activeCard) return;
      const containerRect = container.getBoundingClientRect();
      const cardRect = activeCard.getBoundingClientRect();
      setMascotPosition({
        x: cardRect.left - containerRect.left + 16,
        y: cardRect.top - containerRect.top + 16,
        ready: true,
      });
    };

    const raf = requestAnimationFrame(updatePosition);
    window.addEventListener("resize", updatePosition);
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", updatePosition);
    };
  }, [profile]);

  if (!profile || !selectedPreset || !activeTheme) {
    if (loadError) {
      return (
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <Shield className="h-5 w-5 text-muted-foreground" />
              <CardTitle className="text-base">Agent page failed to load</CardTitle>
            </div>
          </CardHeader>
          <CardContent className="space-y-3 text-sm text-muted-foreground">
            <p>{loadError}</p>
            <p>If you just changed dashboard code, rebuild the frontend and restart the dashboard process.</p>
          </CardContent>
        </Card>
      );
    }
    return (
      <div className="flex items-center justify-center py-24">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      </div>
    );
  }

  const isBuiltIn = selectedPreset.built_in;
  const isEditablePreset = Boolean(selectedSlug);
  const selectedTheme = getPresetTheme(previewPreset || selectedPreset);
  const activePresetCards = profile.presets.map((preset) => {
    if (previewPreset && preset.slug === selectedSlug) return previewPreset;
    return preset;
  });

  const scrollToRef = (ref: { current: HTMLDivElement | null }) => {
    ref.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  const setField = (key: keyof EditorState, value: string) => {
    setEditor((current) => ({ ...current, [key]: value }));
  };

  const handleEmojiSelect = (emoji: string) => {
    setField("emoji", emoji);
    setEmojiPickerOpen(false);
    setEmojiSearch("");
  };

  const handleSelectPreset = (preset: AgentPresetDetail) => {
    setSelectedSlug(preset.slug);
    setEditor(presetToEditor(preset));
    setStatus("");
  };

  const openPreset = (preset: AgentPresetDetail) => {
    handleSelectPreset(preset);
    scrollToRef(editorRef);
  };

  const handleCreateFromTemplate = (template: "default" | "lead-hunter" | "flight-finder" | "blank") => {
    setSelectedSlug("");
    setEditor(buildTemplate(template));
    setStatus(`Loaded ${template} template.`);
  };

  const createNewPreset = (template: "default" | "lead-hunter" | "flight-finder" | "blank" = "blank") => {
    handleCreateFromTemplate(template);
    scrollToRef(editorRef);
  };

  const handleSave = async () => {
    setSaving(true);
    setStatus("");
    try {
      const payload = buildPayload();
      if (isEditablePreset) {
        const updated = await api.updateAgent(selectedSlug, payload);
        await load(updated.slug);
        setStatus(`Saved ${updated.name}.`);
      } else {
        const created = await api.createAgent(payload);
        await load(created.slug);
        setStatus(`Created ${created.name}.`);
      }
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Could not save agent preset.");
    } finally {
      setSaving(false);
    }
  };

  const handleActivate = async (slugOverride?: string) => {
    try {
      const slug = slugOverride || selectedSlug || editor.slug;
      await api.activateAgent(slug);
      await load(slug);
      setStatus(`Activated ${slug}.`);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Could not activate preset.");
    }
  };

  const handleDelete = async () => {
    if (isBuiltIn) return;
    try {
      await api.deleteAgent(selectedSlug);
      await load("default");
      setStatus(`Deleted ${selectedSlug}.`);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Could not delete preset.");
    }
  };

  return (
    <div className="flex flex-col gap-6">
      <Card className="overflow-hidden rounded-[20px] border border-emerald-200/10 bg-[#071614] shadow-[0_12px_32px_rgba(0,0,0,0.22)]">
        <CardHeader className="border-b border-emerald-200/10 pb-5">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
            <div className="space-y-3">
              <div className="flex items-center gap-4">
                <div className="agent-avatar-shell h-12 w-12 border border-emerald-200/10 bg-white/[0.04] text-[#e6eaf0] shadow-none">
                  <Sparkles className="h-2.5 w-2.5 stroke-[1.35]" />
                </div>
                <div>
                  <CardTitle className="font-expanded text-3xl uppercase tracking-[0.14em] text-[#E6EAF0]">Agents</CardTitle>
                  <p className="mt-1 text-sm text-[#9AA4B2]">
                    Deploy, manage, and monitor your specialized AI agents.
                  </p>
                </div>
              </div>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button className="rounded-full border border-[#4F8CFF]/25 bg-[#4F8CFF] px-5 text-[0.72rem] uppercase tracking-[0.14em] text-white shadow-none hover:bg-[#679dff]" onClick={() => createNewPreset("blank")}>
                <Plus className="h-3.5 w-3.5" /> New Agent
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent className="pt-6">
          <div ref={gridRef} className="agent-stage-grid relative">
            <div
              className={cn(
                "agent-stage-mascot hidden",
                activeTheme.glowClass,
                !mascotPosition.ready && "opacity-0",
              )}
              style={{ transform: `translate(${mascotPosition.x}px, ${mascotPosition.y}px)` }}
            >
              <div className={cn("agent-avatar-shell h-12 w-12 border text-xl", activeTheme.avatarClass)}>
                {renderPresetAvatar(profile.current_preset, "agent-avatar-core", "h-4 w-4")}
              </div>
            </div>

            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
              {activePresetCards.map((preset) => {
                const theme = getPresetTheme(preset);
                const pages = pluginPagesBySlug[preset.slug] || [];
                const isSelectedPreset = selectedSlug === preset.slug;
                const openActionClass = "inline-flex h-9 items-center justify-center gap-2 whitespace-nowrap rounded-full border border-white/8 bg-white/[0.04] px-3.5 text-[0.68rem] font-display uppercase tracking-[0.16em] text-[#E6EAF0] transition-colors hover:border-white/12 hover:bg-white/[0.06]";
                return (
                  <div
                    key={preset.slug}
                    ref={(node) => {
                      cardRefs.current[preset.slug] = node;
                    }}
                    className={cn(
                      "agent-preset-card group relative overflow-hidden rounded-[16px] border px-5 py-5 text-left shadow-[0_12px_28px_rgba(0,0,0,0.2)] transition-all duration-200 hover:-translate-y-[2px]",
                      theme.cardClass,
                      theme.hoverClass,
                      theme.glowClass,
                      isSelectedPreset && theme.selectedClass,
                      preset.active && theme.activeClass,
                    )}
                    data-active={preset.active}
                    data-selected={isSelectedPreset}
                  >
                    <div className={cn("absolute inset-0 bg-gradient-to-br opacity-40", theme.stageClass)} />
                    <div className="relative flex h-full flex-col gap-4">
                      <div className="flex items-start justify-between gap-3">
                        <div className="flex min-w-0 items-center gap-3">
                          <div className={cn("agent-avatar-shell h-11 w-11 shrink-0 overflow-hidden border bg-white/[0.04] text-[#E6EAF0] shadow-none", theme.avatarClass)}>
                            {renderPresetCardAvatar(preset, "h-[8px] w-[8px]")}
                          </div>
                          <div className="min-w-0">
                            <div className="font-sans text-[1.1rem] font-medium tracking-[0.01em] text-[#E6EAF0]">{preset.name}</div>
                            <div className="mt-1 flex flex-wrap items-center gap-3 text-[0.76rem] text-[#9AA4B2]">
                              {preset.active ? (
                                <span className="inline-flex items-center gap-2 text-[#cfe0ff]">
                                  <span className="h-2 w-2 rounded-full bg-[#4F8CFF]" />
                                  Active
                                </span>
                              ) : null}
                              <span>{getPresetModeLabel(preset)}</span>
                            </div>
                          </div>
                          {pages[0] ? (
                            <Link to={pages[0].agentPage?.path || pages[0].tab.path} className={openActionClass}>
                              <Compass className="h-3.5 w-3.5" /> Open
                            </Link>
                          ) : (
                            <button type="button" className={openActionClass} onClick={() => openPreset(preset)}>
                              <SquareTerminal className="h-3.5 w-3.5" /> Open
                            </button>
                          )}
                        </div>
                        <button
                          type="button"
                          aria-label={`Configure ${preset.name}`}
                          onClick={() => openPreset(preset)}
                          className="inline-flex h-9 w-9 items-center justify-center rounded-full border border-emerald-200/10 bg-white/[0.04] text-[#9AA4B2] transition-colors hover:border-emerald-200/20 hover:text-[#E6EAF0]"
                        >
                          <Settings className="h-4 w-4" />
                        </button>
                      </div>

                      <div className="space-y-2">
                        <p className="line-clamp-2 max-w-[36ch] text-[0.92rem] leading-6 text-[#9AA4B2]">{summarizePreset(preset)}</p>
                      </div>

                      <div className="mt-auto text-[0.78rem] text-[#6B7280]">
                        {formatTokenCount(profile.model.effective_context_length || 0)} context
                        {cronCountByAgent[preset.slug] ? ` • ${cronCountByAgent[preset.slug]} cron job${cronCountByAgent[preset.slug] > 1 ? "s" : ""}` : ""}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </CardContent>
      </Card>

      <div ref={editorRef} className="grid gap-6">
        <Card className="rounded-[20px] border border-emerald-200/10 bg-[#0b1a18] shadow-[0_12px_32px_rgba(0,0,0,0.2)]">
          <CardHeader className="border-b border-emerald-200/10">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
              <div>
                <CardTitle className="font-expanded text-xl uppercase tracking-[0.12em] text-[#E6EAF0]">Agent editor</CardTitle>
                <p className="mt-2 text-sm text-[#9AA4B2]">
                  Choose which preset to edit here.
                </p>
              </div>
              <div className="w-full sm:w-[300px]">
                <Label htmlFor="agent-editor-select" className="text-[0.68rem] uppercase tracking-[0.16em] text-[#6B7280]">Preset shown in editor</Label>
                <Select
                  id="agent-editor-select"
                  value={selectedSlug}
                  onValueChange={(value) => {
                    const preset = profile.presets.find((item) => item.slug === value);
                    if (preset) handleSelectPreset(preset);
                  }}
                >
                  {profile.presets.map((preset) => (
                    <SelectOption key={preset.slug} value={preset.slug}>{preset.name}</SelectOption>
                  ))}
                </Select>
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-5">
            {status && <div className="rounded-[14px] border border-emerald-200/10 bg-[#071614] px-4 py-3 text-sm text-[#E6EAF0]">{status}</div>}

            <div className="rounded-[16px] border border-emerald-200/10 bg-[#071614] p-5">
              <div className="grid gap-4 md:grid-cols-[72px_1fr] md:items-start">
                <div className={cn("agent-avatar-shell h-14 w-14 border text-3xl", selectedTheme.avatarClass)}>
                  {renderPresetAvatar(previewPreset || selectedPreset, "text-[0.95rem]", "h-3 w-3")}
                </div>
                <div className="space-y-3">
                    <div className="flex flex-wrap items-center gap-3 text-sm text-[#9AA4B2]">
                      {selectedPreset.active ? (
                        <span className="inline-flex items-center gap-2 text-[#cfe0ff]">
                          <span className="h-2 w-2 rounded-full bg-[#4F8CFF]" />
                          Active
                        </span>
                      ) : null}
                      <span>{selectedTheme.label}</span>
                      <span className="text-[#6B7280]">{(previewPreset || selectedPreset).slug}</span>
                    </div>
                    <div>
                      <div className="font-sans text-[1.35rem] font-medium tracking-[0.01em] text-[#E6EAF0]">{(previewPreset || selectedPreset).name}</div>
                      <p className="mt-2 max-w-2xl text-sm leading-6 text-[#9AA4B2]">{summarizePreset(previewPreset || selectedPreset)}</p>
                    </div>
                </div>
              </div>
            </div>

            {isDirty && (
              <div className="rounded-[14px] border border-emerald-200/10 bg-[#071614] px-4 py-3 text-sm text-[#E6EAF0]">
                You have unsaved changes for this preset.
              </div>
            )}
            {isBuiltIn && (
              <div className="rounded-[14px] border border-emerald-200/10 bg-[#071614] px-4 py-4 text-sm leading-6 text-[#9AA4B2]">
                Saving the default preset updates the main <code>~/.hermes/SOUL.md</code> plus its saved preset metadata. Saving built-in presets like Lead Hunter updates their editable preset state directly from here.
              </div>
            )}

            <div className="grid gap-4 md:grid-cols-[220px_1fr_1fr]">
              <div ref={emojiPickerRef} className="space-y-2">
                <Label htmlFor="agent-emoji-picker">Emoji</Label>
                <div className="relative">
                  <button
                    id="agent-emoji-picker"
                    type="button"
                    onClick={() => setEmojiPickerOpen((open) => !open)}
                    className="flex w-full items-center justify-between rounded-[18px] border border-border bg-background/40 px-3 py-3 text-left transition-colors hover:border-foreground/25"
                  >
                    <span className="flex items-center gap-3">
                      <span className="inline-flex h-12 w-12 items-center justify-center rounded-full border border-border bg-muted/30 text-2xl leading-none">
                        {editor.emoji || "🤖"}
                      </span>
                      <span>
                        <span className="block text-sm text-foreground">Choose card emoji</span>
                        <span className="block text-xs text-muted-foreground">Updates the selected agent card live</span>
                      </span>
                    </span>
                    <Sparkles className="h-4 w-4 text-muted-foreground" />
                  </button>
                  {emojiPickerOpen ? (
                    <div className="absolute left-0 z-30 mt-2 w-[320px] rounded-[22px] border border-border bg-card/96 p-3 shadow-[0_20px_70px_rgba(0,0,0,0.35)] backdrop-blur-xl">
                      <div className="relative mb-3">
                        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                        <Input value={emojiSearch} onChange={(e) => setEmojiSearch(e.target.value)} placeholder="Filter emoji" className="pl-9" />
                      </div>
                      <div className="max-h-[280px] space-y-3 overflow-y-auto pr-1">
                        {EMOJI_GROUPS.map((group) => {
                          const emojis = group.emojis.filter((emoji) => filteredPickerEmojis.includes(emoji));
                          if (!emojis.length) return null;
                          return (
                            <div key={group.label} className="space-y-2">
                              <div className="text-[0.68rem] uppercase tracking-[0.16em] text-muted-foreground">{group.label}</div>
                              <div className="grid grid-cols-5 gap-2">
                                {emojis.map((emoji) => (
                                  <button
                                    key={`${group.label}-${emoji}`}
                                    type="button"
                                    onClick={() => handleEmojiSelect(emoji)}
                                    className={cn(
                                      "inline-flex h-12 items-center justify-center rounded-2xl border border-border bg-background/35 text-2xl leading-none transition-all hover:-translate-y-0.5 hover:border-foreground/25 hover:bg-muted/30",
                                      editor.emoji === emoji && "border-foreground/35 bg-muted/40",
                                    )}
                                  >
                                    {emoji}
                                  </button>
                                ))}
                              </div>
                            </div>
                          );
                        })}
                        {!filteredPickerEmojis.length ? (
                          <div className="rounded-2xl border border-dashed border-border p-4 text-sm text-muted-foreground">
                            No matching emoji in this quick picker.
                          </div>
                        ) : null}
                      </div>
                    </div>
                  ) : null}
                </div>
              </div>
              <div className="space-y-2">
                <Label htmlFor="agent-name">Name</Label>
                <Input id="agent-name" value={editor.name} onChange={(e) => setField("name", e.target.value)} />
              </div>
              <div className="space-y-2">
                <Label htmlFor="agent-slug">Slug</Label>
                <Input id="agent-slug" value={editor.slug} onChange={(e) => setField("slug", e.target.value)} disabled={Boolean(selectedSlug)} />
              </div>
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="agent-role">Role</Label>
                <Input id="agent-role" value={editor.role} onChange={(e) => setField("role", e.target.value)} />
              </div>
              <div className="space-y-2">
                <Label htmlFor="agent-goal">Goal</Label>
                <Input id="agent-goal" value={editor.goal} onChange={(e) => setField("goal", e.target.value)} />
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="agent-description">Description</Label>
              <Input id="agent-description" value={editor.description} onChange={(e) => setField("description", e.target.value)} />
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="agent-personality">Default personality</Label>
                <Select value={editor.personality} onValueChange={(value) => setField("personality", value)} id="agent-personality">
                  <SelectOption value="">None</SelectOption>
                  {profile.available_personalities.map((personality) => (
                    <SelectOption key={personality} value={personality}>{personality}</SelectOption>
                  ))}
                </Select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="agent-skills">Default skills</Label>
                <Input id="agent-skills" value={editor.default_skills} onChange={(e) => setField("default_skills", e.target.value)} placeholder="skill-a, skill-b" />
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="agent-soul">SOUL.md</Label>
              <p className="text-xs text-muted-foreground">Primary persona and operating instructions for this preset.</p>
              <textarea id="agent-soul" className={textareaClass} value={editor.soul_content} onChange={(e) => setField("soul_content", e.target.value)} />
            </div>

            <div className="space-y-2">
              <Label htmlFor="agent-agents">AGENTS.md</Label>
              <p className="text-xs text-muted-foreground">Optional workflow or project-specific instructions for this preset.</p>
              <textarea id="agent-agents" className={textareaClass} value={editor.agents_content} onChange={(e) => setField("agents_content", e.target.value)} />
            </div>

            <div className="flex flex-wrap gap-2">
              <Button onClick={handleSave} disabled={saving || (isEditablePreset ? !isDirty : false)}>{saving ? "Saving…" : isEditablePreset ? "Save preset" : "Create preset"}</Button>
              <Button variant="outline" onClick={() => handleActivate()}>
                <Rocket className="h-3.5 w-3.5" /> Activate
              </Button>
              <Button variant="destructive" onClick={handleDelete} disabled={isBuiltIn}><Trash2 className="h-3.5 w-3.5" /> Delete</Button>
            </div>
          </CardContent>
        </Card>

      </div>
    </div>
  );
}
