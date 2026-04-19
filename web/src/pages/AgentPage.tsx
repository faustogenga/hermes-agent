import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  Bot,
  Brain,
  CopyPlus,
  Eye,
  Gauge,
  Rocket,
  Shield,
  Sparkles,
  Trash2,
  Wrench,
} from "lucide-react";
import { api } from "@/lib/api";
import type { AgentPresetDetail, AgentProfileResponse, CronJob, PluginManifestResponse } from "@/lib/api";
import { formatTokenCount } from "@/lib/format";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
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

const textareaClass = "min-h-[140px] w-full border border-border bg-background/40 px-3 py-2 font-courier text-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-foreground/30 focus-visible:border-foreground/25";

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

function buildTemplate(template: "default" | "lead-hunter" | "blank"): EditorState {
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

export default function AgentPage() {
  const [profile, setProfile] = useState<AgentProfileResponse | null>(null);
  const [agentPlugins, setAgentPlugins] = useState<PluginManifestResponse[]>([]);
  const [cronJobs, setCronJobs] = useState<CronJob[]>([]);
  const [selectedSlug, setSelectedSlug] = useState<string>("");
  const [editor, setEditor] = useState<EditorState>(buildTemplate("blank"));
  const [status, setStatus] = useState<string>("");
  const [saving, setSaving] = useState(false);
  const [loadError, setLoadError] = useState<string>("");

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

  const selectedPreset = useMemo(() => {
    if (!profile) return null;
    return profile.presets.find((preset) => preset.slug === selectedSlug) || profile.current_preset;
  }, [profile, selectedSlug]);

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

  const selectedAgentPages = useMemo(
    () => agentPlugins.filter((plugin) => plugin.agentPage?.slug === selectedSlug),
    [agentPlugins, selectedSlug],
  );

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

  if (!profile || !selectedPreset) {
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

  const caps = profile.model.capabilities ?? {};
  const isBuiltIn = selectedPreset.built_in;
  const isEditablePreset = Boolean(selectedSlug) && !isBuiltIn;
  const effectiveSlug = selectedSlug || editor.slug || profile.active_preset;
  const assignedCronJobs = cronJobs.filter((job) => (job.agent_name || "default") === effectiveSlug);

  const nextAvailableSlug = (base: string) => {
    const normalizedBase = (base || "new-agent").trim().toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "") || "new-agent";
    const existing = new Set((profile.presets || []).map((preset) => preset.slug));
    if (!existing.has(normalizedBase)) return normalizedBase;
    let index = 2;
    while (existing.has(`${normalizedBase}-${index}`)) {
      index += 1;
    }
    return `${normalizedBase}-${index}`;
  };

  const setField = (key: keyof EditorState, value: string) => {
    setEditor((current) => ({ ...current, [key]: value }));
  };

  const handleSelectPreset = (preset: AgentPresetDetail) => {
    setSelectedSlug(preset.slug);
    setEditor(presetToEditor(preset));
    setStatus("");
  };

  const handleCreateFromTemplate = (template: "default" | "lead-hunter" | "blank") => {
    setSelectedSlug("");
    setEditor(buildTemplate(template));
    setStatus(`Loaded ${template} template.`);
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
        const duplicateMode = isBuiltIn;
        const nextPayload = { ...payload };
        if (duplicateMode) {
          const unchangedSlug = !nextPayload.slug || nextPayload.slug === selectedPreset.slug;
          const unchangedName = !nextPayload.name || nextPayload.name === selectedPreset.name;
          if (unchangedName) {
            nextPayload.name = `${selectedPreset.name} Copy`;
          }
          if (unchangedSlug) {
            nextPayload.slug = nextAvailableSlug(`${selectedPreset.slug}-copy`);
          }
        }
        const created = await api.createAgent(nextPayload);
        await load(created.slug);
        setStatus(duplicateMode ? `Duplicated ${selectedPreset.name} to ${created.name}.` : `Created ${created.name}.`);
      }
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Could not save agent preset.");
    } finally {
      setSaving(false);
    }
  };

  const handleActivate = async () => {
    try {
      const slug = selectedSlug || editor.slug;
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
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <Bot className="h-5 w-5 text-muted-foreground" />
            <CardTitle className="text-base">Active agent: {profile.current_preset.name}</CardTitle>
          </div>
        </CardHeader>
        <CardContent className="grid gap-4 lg:grid-cols-[1.2fr_0.8fr]">
          <div className="space-y-4">
            <div>
              <div className="text-xs uppercase tracking-[0.14em] text-muted-foreground">Role</div>
              <p className="mt-1 text-lg font-semibold leading-snug">{profile.role}</p>
            </div>
            <div>
              <div className="text-xs uppercase tracking-[0.14em] text-muted-foreground">Description</div>
              <p className="mt-1 text-sm leading-6 text-muted-foreground">{profile.description}</p>
            </div>
            {profile.current_preset.goal && (
              <div>
                <div className="text-xs uppercase tracking-[0.14em] text-muted-foreground">Goal</div>
                <p className="mt-1 text-sm leading-6 text-muted-foreground">{profile.current_preset.goal}</p>
              </div>
            )}
            {profile.personality_prompt && (
              <div>
                <div className="text-xs uppercase tracking-[0.14em] text-muted-foreground">Active personality prompt</div>
                <pre className="mt-1 whitespace-pre-wrap border border-border bg-muted/30 p-3 text-xs leading-5 text-foreground/90">
                  {profile.personality_prompt}
                </pre>
              </div>
            )}
          </div>

          <div className="space-y-3">
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-1">
              <div className="border border-border p-3">
                <div className="flex items-center gap-2 text-xs uppercase tracking-[0.14em] text-muted-foreground">
                  <Rocket className="h-3.5 w-3.5" /> Preset
                </div>
                <div className="mt-2 text-sm font-medium break-all">{profile.active_preset}</div>
              </div>
              <div className="border border-border p-3">
                <div className="flex items-center gap-2 text-xs uppercase tracking-[0.14em] text-muted-foreground">
                  <Sparkles className="h-3.5 w-3.5" /> Personality
                </div>
                <div className="mt-2 text-sm font-medium">{profile.active_personality || "default"}</div>
              </div>
              <div className="border border-border p-3">
                <div className="flex items-center gap-2 text-xs uppercase tracking-[0.14em] text-muted-foreground">
                  <Wrench className="h-3.5 w-3.5" /> Model
                </div>
                <div className="mt-2 text-sm font-medium break-all">{profile.model.model || "unknown"}</div>
                <div className="mt-1 text-xs text-muted-foreground">{profile.model.provider || "provider not set"}</div>
              </div>
              <div className="border border-border p-3">
                <div className="flex items-center gap-2 text-xs uppercase tracking-[0.14em] text-muted-foreground">
                  <Gauge className="h-3.5 w-3.5" /> Context window
                </div>
                <div className="mt-2 text-sm font-medium">
                  {profile.model.effective_context_length > 0 ? formatTokenCount(profile.model.effective_context_length) : "unknown"}
                </div>
              </div>
            </div>

            <div className="border border-border p-3">
              <div className="flex items-center gap-2 text-xs uppercase tracking-[0.14em] text-muted-foreground">
                <Shield className="h-3.5 w-3.5" /> Capabilities
              </div>
              <div className="mt-3 flex flex-wrap gap-2">
                {caps.supports_tools && <Badge variant="success"><Wrench className="mr-1 h-3 w-3" />Tools</Badge>}
                {caps.supports_vision && <Badge variant="outline"><Eye className="mr-1 h-3 w-3" />Vision</Badge>}
                {caps.supports_reasoning && <Badge variant="outline"><Brain className="mr-1 h-3 w-3" />Reasoning</Badge>}
                {caps.model_family && <Badge variant="outline">{caps.model_family}</Badge>}
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-6 xl:grid-cols-[280px_1fr]">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Agent library</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {profile.presets.map((preset) => (
              <button
                key={preset.slug}
                type="button"
                onClick={() => handleSelectPreset(preset)}
                className={`w-full border p-3 text-left transition-colors ${selectedSlug === preset.slug ? "border-foreground/40 bg-foreground/5" : "border-border hover:bg-foreground/5"}`}
              >
                <div className="flex items-center justify-between gap-2">
                  <div className="font-display text-xs uppercase tracking-[0.1em]">{preset.emoji || "🤖"} {preset.name}</div>
                  {preset.active && <Badge variant="success">Active</Badge>}
                </div>
                <div className="mt-2 text-xs text-muted-foreground break-all">{preset.slug}</div>
                <div className="mt-2 text-xs text-muted-foreground line-clamp-3">{preset.description || preset.role || "No description yet."}</div>
              </button>
            ))}
            <div className="space-y-2 border-t border-border pt-3">
              <div className="text-xs uppercase tracking-[0.14em] text-muted-foreground">Create from template</div>
              <div className="grid gap-2">
                <Button variant="outline" onClick={() => handleCreateFromTemplate("default")}><CopyPlus className="h-3.5 w-3.5" /> Default</Button>
                <Button variant="outline" onClick={() => handleCreateFromTemplate("lead-hunter")}><CopyPlus className="h-3.5 w-3.5" /> Lead hunter</Button>
                <Button variant="outline" onClick={() => handleCreateFromTemplate("blank")}><CopyPlus className="h-3.5 w-3.5" /> Blank</Button>
              </div>
            </div>
          </CardContent>
        </Card>

        <div className="space-y-6">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between gap-3">
                <CardTitle className="text-base">Agent editor</CardTitle>
                <Button onClick={handleSave} disabled={saving || (isEditablePreset ? !isDirty : false)}>
                  {saving ? "Saving…" : isEditablePreset ? "Save preset" : isBuiltIn ? "Duplicate preset" : "Create preset"}
                </Button>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              {status && <div className="border border-border bg-muted/30 p-3 text-sm text-muted-foreground">{status}</div>}
              {isDirty && !isBuiltIn && (
                <div className="border border-border bg-muted/20 p-3 text-sm text-muted-foreground">
                  You have unsaved changes for this preset.
                </div>
              )}
              {isBuiltIn && (
                <div className="border border-border bg-muted/30 p-3 text-sm text-muted-foreground">
                  The built-in default preset uses the root <code>~/.hermes/SOUL.md</code>. Editing here creates a duplicate preset you can customize safely.
                </div>
              )}
              <div className="grid gap-4 md:grid-cols-[96px_1fr_1fr]">
                <div className="space-y-2">
                  <Label htmlFor="agent-emoji">Emoji</Label>
                  <Input id="agent-emoji" value={editor.emoji} onChange={(e) => setField("emoji", e.target.value)} maxLength={4} />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="agent-name">Name</Label>
                  <Input id="agent-name" value={editor.name} onChange={(e) => setField("name", e.target.value)} />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="agent-slug">Slug</Label>
                  <Input id="agent-slug" value={editor.slug} onChange={(e) => setField("slug", e.target.value)} disabled={Boolean(selectedSlug) && !isBuiltIn} />
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
                <Button onClick={handleSave} disabled={saving || (isEditablePreset ? !isDirty : false)}>{saving ? "Saving…" : isEditablePreset ? "Save preset" : isBuiltIn ? "Duplicate preset" : "Create preset"}</Button>
                <Button variant="outline" onClick={handleActivate}>Activate</Button>
                <Button variant="destructive" onClick={handleDelete} disabled={isBuiltIn}><Trash2 className="h-3.5 w-3.5" /> Delete</Button>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">Assigned cron jobs</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <p className="text-sm text-muted-foreground">
                Jobs assigned to <code>{effectiveSlug}</code>. Create or reassign them in <Link to="/cron" className="underline underline-offset-4">/cron</Link> using the agent preset selector.
              </p>
              {assignedCronJobs.length === 0 ? (
                <div className="border border-dashed border-border p-3 text-sm text-muted-foreground">
                  No cron jobs are currently assigned to this preset.
                </div>
              ) : (
                <div className="space-y-2">
                  {assignedCronJobs.map((job) => (
                    <div key={job.id} className="border border-border p-3">
                      <div className="flex flex-wrap items-center gap-2">
                        <div className="font-medium">{job.name || job.prompt.slice(0, 80)}</div>
                        <Badge variant="outline">{job.schedule_display}</Badge>
                        <Badge variant="outline">{job.state}</Badge>
                      </div>
                      <p className="mt-2 text-sm text-muted-foreground">
                        {job.prompt.slice(0, 180)}{job.prompt.length > 180 ? "…" : ""}
                      </p>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          {selectedAgentPages.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Agent pages</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <p className="text-sm text-muted-foreground">
                  These pages belong to the selected agent preset rather than the main dashboard navigation.
                </p>
                <div className="flex flex-wrap gap-2">
                  {selectedAgentPages.map((plugin) => (
                    <Link
                      key={plugin.name}
                      to={plugin.agentPage?.path || plugin.tab.path}
                      className="inline-flex h-9 items-center justify-center gap-2 whitespace-nowrap border border-border bg-transparent px-4 py-2 font-display text-xs uppercase tracking-[0.1em] transition-colors hover:bg-foreground/10 hover:text-foreground"
                    >
                      {plugin.agentPage?.label || plugin.label}
                    </Link>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
