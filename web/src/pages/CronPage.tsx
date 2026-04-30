import { useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  CalendarDays,
  Clock,
  Pause,
  Pencil,
  Play,
  Save,
  Trash2,
  X,
  Zap,
} from "lucide-react";
import { api } from "@/lib/api";
import type { AgentPresetSummary, CronJob } from "@/lib/api";
import { useToast } from "@/hooks/useToast";
import { Toast } from "@/components/Toast";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectOption } from "@/components/ui/select";
import { useI18n } from "@/i18n";
import { cn } from "@/lib/utils";

type EditDraft = {
  name: string;
  prompt: string;
  schedule: string;
};

type ScheduleBuilderPattern = "once" | "twice" | "three" | "custom";

type ScheduleBuilderState = {
  pattern: ScheduleBuilderPattern;
  firstHour: string;
  firstMinute: string;
  secondHour: string;
  secondMinute: string;
  thirdHour: string;
  thirdMinute: string;
};

type JobTheme = {
  label: string;
  emoji: string;
  cardClass: string;
  bubbleClass: string;
  accentBadgeClass: string;
  subtleBadgeClass: string;
  statusBadgeClass: string;
  timelineDotClass: string;
  timelineBarClass: string;
  pillClass: string;
  actionButtonClass: string;
};

type TimelineEntry = {
  id: string;
  title: string;
  startMinute: number;
  endMinute: number;
  durationMinutes: number;
  startLabel: string;
  endLabel: string;
  widthPercent: number;
  leftPercent: number;
  overlapRisk: boolean;
  cadence: string;
  theme: JobTheme;
};

function formatTime(iso?: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function truncatePrompt(prompt: string, limit = 120): string {
  if (prompt.length <= limit) return prompt;
  return `${prompt.slice(0, limit).trim()}…`;
}

function padTime(value: number): string {
  return String(value).padStart(2, "0");
}

function formatMinuteOfDay(totalMinutes: number): string {
  const normalized = ((totalMinutes % 1440) + 1440) % 1440;
  const hours = Math.floor(normalized / 60);
  const minutes = normalized % 60;
  return `${padTime(hours)}:${padTime(minutes)}`;
}

function describePartOfDay(hour: number): string {
  if (hour < 6) return "overnight";
  if (hour < 12) return "morning";
  if (hour < 17) return "afternoon";
  if (hour < 21) return "evening";
  return "night";
}

function parseCronNumberList(field: string, min: number, max: number): number[] | null {
  if (!field) return null;
  const values = new Set<number>();
  const parts = field.split(",").map((part) => part.trim()).filter(Boolean);

  for (const part of parts) {
    if (part === "*") {
      for (let i = min; i <= max; i += 1) values.add(i);
      continue;
    }

    const stepMatch = part.match(/^\*\/(\d+)$/);
    if (stepMatch) {
      const step = Number(stepMatch[1]);
      if (!step) return null;
      for (let i = min; i <= max; i += step) values.add(i);
      continue;
    }

    const rangeMatch = part.match(/^(\d+)-(\d+)(?:\/(\d+))?$/);
    if (rangeMatch) {
      const start = Number(rangeMatch[1]);
      const end = Number(rangeMatch[2]);
      const step = Number(rangeMatch[3] || 1);
      if (Number.isNaN(start) || Number.isNaN(end) || Number.isNaN(step) || step <= 0) return null;
      for (let i = start; i <= end; i += step) {
        if (i >= min && i <= max) values.add(i);
      }
      continue;
    }

    const raw = Number(part);
    if (Number.isNaN(raw)) return null;
    if (raw >= min && raw <= max) values.add(raw);
  }

  return Array.from(values).sort((a, b) => a - b);
}

function getDailyRunSlots(job: Pick<CronJob, "schedule">): number[] {
  const expr = job.schedule?.expr?.trim();
  if (!expr) return [];
  const parts = expr.split(/\s+/);
  if (parts.length < 5) return [];

  const [minuteField, hourField, dayOfMonth, month, dayOfWeek] = parts;
  const isEveryDay = (dayOfMonth === "*" || dayOfMonth === "?")
    && (month === "*" || month === "?")
    && (dayOfWeek === "*" || dayOfWeek === "?");
  if (!isEveryDay) return [];

  const minutes = parseCronNumberList(minuteField, 0, 59);
  const hours = parseCronNumberList(hourField, 0, 23);
  if (!minutes || !hours) return [];

  const slots: number[] = [];
  for (const hour of hours) {
    for (const minute of minutes) {
      slots.push(hour * 60 + minute);
    }
  }

  return Array.from(new Set(slots)).sort((a, b) => a - b);
}

function estimateDurationMinutes(job: Pick<CronJob, "agent_name" | "name" | "prompt">): number {
  const text = `${job.agent_name || ""} ${job.name || ""} ${job.prompt || ""}`.toLowerCase();
  if (text.includes("lead")) return 20;
  if (text.includes("housing") || text.includes("rent") || text.includes("apartment")) return 18;
  if (text.includes("flight") || text.includes("airfare") || text.includes("route tracker")) return 16;
  return 15;
}

function describeDailyCadence(job: Pick<CronJob, "schedule">): string {
  const slots = getDailyRunSlots(job);
  if (!slots.length) return job.schedule.display || "Custom schedule";

  const times = slots.map(formatMinuteOfDay);
  const dayBands = Array.from(new Set(slots.map((slot) => describePartOfDay(Math.floor(slot / 60)))));

  if (slots.length === 1) {
    return `Runs daily at ${times[0]} · ${dayBands[0]}`;
  }

  return `${slots.length} runs/day · ${times.join(", ")} · ${dayBands.join(", ")}`;
}

function getJobTheme(job: Pick<CronJob, "agent_name" | "name" | "prompt">): JobTheme {
  const text = `${job.agent_name || ""} ${job.name || ""} ${job.prompt || ""}`.toLowerCase();

  if (text.includes("lead")) {
    return {
      label: "Lead Hunter",
      emoji: "🎯",
      cardClass: "border-amber-100/18 bg-amber-50/[0.035]",
      bubbleClass: "border-amber-100/24 bg-amber-50/[0.12]",
      accentBadgeClass: "cron-soft-badge cron-soft-badge-amber",
      subtleBadgeClass: "cron-soft-badge-muted cron-soft-badge-amber",
      statusBadgeClass: "cron-soft-badge cron-soft-badge-neutral",
      timelineDotClass: "bg-amber-50 text-slate-800 border-amber-100",
      timelineBarClass: "bg-amber-100/35",
      pillClass: "cron-preset-pill-amber",
      actionButtonClass: "border-white/14 bg-white/[0.05] text-foreground hover:bg-white/[0.10]",
    };
  }

  if (text.includes("flight") || text.includes("airfare") || text.includes("route tracker")) {
    return {
      label: "Flight Finder",
      emoji: "✈️",
      cardClass: "border-sky-100/18 bg-sky-50/[0.035]",
      bubbleClass: "border-sky-100/24 bg-sky-50/[0.12]",
      accentBadgeClass: "cron-soft-badge cron-soft-badge-sky",
      subtleBadgeClass: "cron-soft-badge-muted cron-soft-badge-sky",
      statusBadgeClass: "cron-soft-badge cron-soft-badge-neutral",
      timelineDotClass: "bg-sky-50 text-slate-800 border-sky-100",
      timelineBarClass: "bg-sky-100/35",
      pillClass: "cron-preset-pill-sky",
      actionButtonClass: "border-white/14 bg-white/[0.05] text-foreground hover:bg-white/[0.10]",
    };
  }

  if (text.includes("housing") || text.includes("rent") || text.includes("apartment")) {
    return {
      label: "Housing Hunter",
      emoji: "🏠",
      cardClass: "border-emerald-100/18 bg-emerald-50/[0.035]",
      bubbleClass: "border-emerald-100/24 bg-emerald-50/[0.12]",
      accentBadgeClass: "cron-soft-badge cron-soft-badge-emerald",
      subtleBadgeClass: "cron-soft-badge-muted cron-soft-badge-emerald",
      statusBadgeClass: "cron-soft-badge cron-soft-badge-neutral",
      timelineDotClass: "bg-emerald-50 text-slate-800 border-emerald-100",
      timelineBarClass: "bg-emerald-100/35",
      pillClass: "cron-preset-pill-emerald",
      actionButtonClass: "border-white/14 bg-white/[0.05] text-foreground hover:bg-white/[0.10]",
    };
  }

  return {
    label: "Default",
    emoji: "✨",
    cardClass: "border-emerald-100/18 bg-white/[0.03]",
    bubbleClass: "border-emerald-100/24 bg-white/[0.10]",
    accentBadgeClass: "cron-soft-badge cron-soft-badge-emerald",
    subtleBadgeClass: "cron-soft-badge-muted cron-soft-badge-emerald",
    statusBadgeClass: "cron-soft-badge cron-soft-badge-neutral",
    timelineDotClass: "bg-white text-slate-800 border-emerald-100",
    timelineBarClass: "bg-emerald-100/30",
    pillClass: "cron-preset-pill-emerald",
    actionButtonClass: "border-white/14 bg-white/[0.05] text-foreground hover:bg-white/[0.10]",
  };
}

function makeDraft(job: CronJob): EditDraft {
  return {
    name: job.name || "",
    prompt: job.prompt,
    schedule: job.schedule?.expr || job.schedule_display || "",
  };
}

function parseScheduleBuilderState(schedule: string): ScheduleBuilderState {
  const expr = schedule.trim();
  const parts = expr.split(/\s+/);
  if (parts.length >= 5) {
    const [minuteField, hourField, dayOfMonth, month, dayOfWeek] = parts;
    const isEveryDay = (dayOfMonth === "*" || dayOfMonth === "?")
      && (month === "*" || month === "?")
      && (dayOfWeek === "*" || dayOfWeek === "?");
    const minutes = parseCronNumberList(minuteField, 0, 59);
    const hours = parseCronNumberList(hourField, 0, 23);

    if (isEveryDay && minutes && hours && minutes.length === 1 && hours.length >= 1 && hours.length <= 3) {
      const fill = (idx: number) => ({
        hour: padTime(hours[idx] ?? hours[0] ?? 9),
        minute: padTime(minutes[0] ?? 0),
      });
      const first = fill(0);
      const second = fill(1);
      const third = fill(2);
      return {
        pattern: hours.length === 1 ? "once" : hours.length === 2 ? "twice" : "three",
        firstHour: first.hour,
        firstMinute: first.minute,
        secondHour: second.hour,
        secondMinute: second.minute,
        thirdHour: third.hour,
        thirdMinute: third.minute,
      };
    }
  }

  return {
    pattern: "custom",
    firstHour: "09",
    firstMinute: "00",
    secondHour: "13",
    secondMinute: "00",
    thirdHour: "18",
    thirdMinute: "00",
  };
}

function buildDailyCron(hours: string[], minute: string): string {
  const normalizedHours = hours
    .map((value) => Number(value))
    .filter((value, idx, arr) => !Number.isNaN(value) && value >= 0 && value <= 23 && arr.indexOf(value) === idx)
    .sort((a, b) => a - b)
    .map((value) => String(value));
  const normalizedMinute = String(Math.max(0, Math.min(59, Number(minute) || 0)));
  return `${normalizedMinute} ${normalizedHours.join(",")} * * *`;
}

function expandScheduleBuilderForPattern(
  builder: ScheduleBuilderState,
  pattern: ScheduleBuilderPattern,
): ScheduleBuilderState {
  if (pattern === "custom") {
    return { ...builder, pattern };
  }

  const firstHour = Number(builder.firstHour || "9");
  const fallbackSecond = padTime((firstHour + 6) % 24);
  const fallbackThird = padTime((firstHour + 12) % 24);

  return {
    ...builder,
    pattern,
    secondHour:
      pattern === "once"
        ? builder.secondHour
        : builder.secondHour !== builder.firstHour
          ? builder.secondHour
          : fallbackSecond,
    thirdHour:
      pattern === "three"
        ? (builder.thirdHour !== builder.firstHour && builder.thirdHour !== builder.secondHour
          ? builder.thirdHour
          : fallbackThird)
        : builder.thirdHour,
  };
}

function applyScheduleBuilder(builder: ScheduleBuilderState): string {
  if (builder.pattern === "custom") {
    return "";
  }
  if (builder.pattern === "once") {
    return buildDailyCron([builder.firstHour], builder.firstMinute);
  }
  if (builder.pattern === "twice") {
    return buildDailyCron([builder.firstHour, builder.secondHour], builder.firstMinute);
  }
  return buildDailyCron([builder.firstHour, builder.secondHour, builder.thirdHour], builder.firstMinute);
}

export default function CronPage() {
  const [jobs, setJobs] = useState<CronJob[]>([]);
  const [presets, setPresets] = useState<AgentPresetSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [editingJobId, setEditingJobId] = useState<string | null>(null);
  const [editDrafts, setEditDrafts] = useState<Record<string, EditDraft>>({});
  const [savingJobId, setSavingJobId] = useState<string | null>(null);
  const { toast, showToast } = useToast();
  const { t } = useI18n();

  const presetOptions = presets.length
    ? presets
    : [{ slug: "default", name: "Default" } as AgentPresetSummary];

  const loadJobs = () => {
    api
      .getCronJobs()
      .then(setJobs)
      .catch(() => showToast(t.common.loading, "error"))
      .finally(() => setLoading(false));
  };

  const loadPresets = () => {
    api
      .getAgents()
      .then((data) => setPresets(data.presets))
      .catch(() => setPresets([]));
  };

  useEffect(() => {
    loadPresets();
    loadJobs();
  }, []);

  const hourOptions = Array.from({ length: 24 }, (_, hour) => padTime(hour));
  const minuteOptions = ["00", "05", "10", "15", "20", "30", "40", "45", "50", "55"];

  const timelineEntries = useMemo<TimelineEntry[]>(() => {
    const entries = jobs.flatMap((job) => {
      const slots = getDailyRunSlots(job);
      const durationMinutes = estimateDurationMinutes(job);
      const theme = getJobTheme(job);
      const title = job.name || truncatePrompt(job.prompt, 48);
      const cadence = describeDailyCadence(job);

      return slots.map((startMinute, index) => {
        const endMinute = startMinute + durationMinutes;
        return {
          id: `${job.id}-${index}`,
          title,
          startMinute,
          endMinute,
          durationMinutes,
          startLabel: formatMinuteOfDay(startMinute),
          endLabel: formatMinuteOfDay(endMinute),
          widthPercent: Math.max((durationMinutes / 1440) * 100, 2.2),
          leftPercent: (startMinute / 1440) * 100,
          overlapRisk: false,
          cadence,
          theme,
        };
      });
    }).sort((a, b) => a.startMinute - b.startMinute);

    let runningEnd = -1;
    for (const entry of entries) {
      if (entry.startMinute < runningEnd) entry.overlapRisk = true;
      runningEnd = Math.max(runningEnd, entry.endMinute);
    }

    return entries;
  }, [jobs]);

  const overlapCount = timelineEntries.filter((entry) => entry.overlapRisk).length;
  const longestDuration = timelineEntries.reduce((max, entry) => Math.max(max, entry.durationMinutes), 0);

  const handlePauseResume = async (job: CronJob) => {
    try {
      const isPaused = job.state === "paused";
      if (isPaused) {
        await api.resumeCronJob(job.id);
        showToast(`${t.cron.resume}: "${job.name || job.prompt.slice(0, 30)}"`, "success");
      } else {
        await api.pauseCronJob(job.id);
        showToast(`${t.cron.pause}: "${job.name || job.prompt.slice(0, 30)}"`, "success");
      }
      loadJobs();
    } catch (e) {
      showToast(`${t.status.error}: ${e}`, "error");
    }
  };

  const handleTrigger = async (job: CronJob) => {
    try {
      await api.triggerCronJob(job.id);
      showToast(`${t.cron.triggerNow}: "${job.name || job.prompt.slice(0, 30)}"`, "success");
      loadJobs();
    } catch (e) {
      showToast(`${t.status.error}: ${e}`, "error");
    }
  };

  const handleDelete = async (job: CronJob) => {
    try {
      await api.deleteCronJob(job.id);
      showToast(`${t.common.delete}: "${job.name || job.prompt.slice(0, 30)}"`, "success");
      loadJobs();
    } catch (e) {
      showToast(`${t.status.error}: ${e}`, "error");
    }
  };

  const handleReassignAgent = async (job: CronJob, nextAgentName: string) => {
    try {
      await api.updateCronJob(job.id, { agent_name: nextAgentName || "default" });
      showToast(`Assigned to ${nextAgentName || "default"}`, "success");
      loadJobs();
    } catch (e) {
      showToast(`${t.status.error}: ${e}`, "error");
    }
  };

  const handleStartEdit = (job: CronJob) => {
    setEditingJobId(job.id);
    setEditDrafts((current) => ({
      ...current,
      [job.id]: current[job.id] || makeDraft(job),
    }));
  };

  const handleCancelEdit = (job: CronJob) => {
    setEditingJobId((current) => (current === job.id ? null : current));
    setEditDrafts((current) => ({
      ...current,
      [job.id]: makeDraft(job),
    }));
  };

  const handleDraftChange = (jobId: string, field: keyof EditDraft, value: string) => {
    setEditDrafts((current) => ({
      ...current,
      [jobId]: {
        ...(current[jobId] || { name: "", prompt: "", schedule: "" }),
        [field]: value,
      },
    }));
  };

  const handleScheduleBuilderChange = (
    jobId: string,
    field: keyof ScheduleBuilderState,
    value: string,
  ) => {
    const currentDraft = editDrafts[jobId] || { name: "", prompt: "", schedule: "" };
    const currentBuilder = parseScheduleBuilderState(currentDraft.schedule);
    const nextBuilder = (
      field === "pattern"
        ? expandScheduleBuilderForPattern(currentBuilder, value as ScheduleBuilderPattern)
        : { ...currentBuilder, [field]: value }
    ) as ScheduleBuilderState;
    const nextSchedule = nextBuilder.pattern === "custom"
      ? currentDraft.schedule
      : applyScheduleBuilder(nextBuilder);

    setEditDrafts((current) => ({
      ...current,
      [jobId]: {
        ...currentDraft,
        schedule: nextSchedule,
      },
    }));
  };

  const handleSaveEdit = async (job: CronJob) => {
    const draft = editDrafts[job.id] || makeDraft(job);
    if (!draft.prompt.trim() || !draft.schedule.trim()) {
      showToast("Description and schedule are required", "error");
      return;
    }

    setSavingJobId(job.id);
    try {
      await api.updateCronJob(job.id, {
        name: draft.name.trim(),
        prompt: draft.prompt.trim(),
        schedule: draft.schedule.trim(),
      });
      showToast(`Updated "${draft.name.trim() || job.name || job.id}"`, "success");
      setEditingJobId((current) => (current === job.id ? null : current));
      loadJobs();
    } catch (e) {
      showToast(`${t.status.error}: ${e}`, "error");
    } finally {
      setSavingJobId(null);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <Toast toast={toast} />

      <div className="flex flex-col gap-3">
        <div className="flex items-center justify-between gap-3">
          <h2 className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
            <Clock className="h-4 w-4" />
            {t.cron.scheduledJobs} ({jobs.length})
          </h2>
        </div>

        <Card className="cron-schedule-overview-card overflow-hidden rounded-[28px] border-white/10 bg-white/[0.03] shadow-none">
          <CardHeader className="border-b border-white/8 bg-transparent">
            <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
              <div className="space-y-1.5">
                <Badge className="cron-soft-badge cron-soft-badge-neutral w-fit" variant="outline">
                  🗓️ Daily schedule map
                </Badge>
                <CardTitle className="flex items-center gap-2 text-base text-white/95">
                  <CalendarDays className="h-4 w-4" />
                  Today’s run rhythm
                </CardTitle>
                <p className="max-w-3xl text-sm text-muted-foreground">
                  Window view assumes each cron takes roughly 15–20 minutes. Use this to avoid overlapping runs and shift exact execution times when needed.
                </p>
              </div>
              <div className="flex flex-wrap gap-2 text-[0.72rem] text-muted-foreground">
                <span className="cron-meta-chip">{timelineEntries.length} run windows/day</span>
                <span className="cron-meta-chip">Longest run ≈ {longestDuration || 0} min</span>
                <span className="cron-meta-chip">{overlapCount ? `${overlapCount} overlap risk` : "No overlap risk"}</span>
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-4 bg-transparent">
            {timelineEntries.length > 0 ? (
              <>
                <div className="flex items-center justify-between text-[0.68rem] uppercase tracking-[0.14em] text-muted-foreground/75">
                  <span>00:00</span>
                  <span>06:00</span>
                  <span>12:00</span>
                  <span>18:00</span>
                  <span>24:00</span>
                </div>
                <div className="cron-timeline-track relative h-16 overflow-visible rounded-[22px] border border-white/10 bg-white/[0.04]">
                  <div className="absolute inset-0 bg-[linear-gradient(90deg,rgba(255,255,255,0.03)_1px,transparent_1px)] bg-[length:25%_100%]" />
                  {timelineEntries.map((entry) => (
                    <div
                      key={entry.id}
                      className="absolute top-1/2 -translate-y-1/2"
                      style={{ left: `calc(${entry.leftPercent}% - 12px)` }}
                      title={`${entry.title} · ${entry.startLabel}–${entry.endLabel} · ${entry.durationMinutes} min`}
                    >
                      <div className={cn("absolute left-[12px] top-1/2 h-[3px] -translate-y-1/2 rounded-full", entry.theme.timelineBarClass)} style={{ width: `calc(${entry.widthPercent}% + 8px)` }} />
                      <div className={cn("cron-timeline-dot relative z-10 flex h-7 w-7 items-center justify-center rounded-full border text-sm shadow-none", entry.theme.timelineDotClass, entry.overlapRisk && "ring-1 ring-amber-200/80")}>
                        {entry.theme.emoji}
                      </div>
                    </div>
                  ))}
                </div>
                <div className="grid gap-2 lg:grid-cols-2">
                  {timelineEntries.map((entry) => (
                    <div key={`${entry.id}-summary`} className="cron-schedule-row flex items-start justify-between gap-3 rounded-[20px] border border-white/8 bg-white/[0.035] px-3 py-3">
                      <div className="min-w-0 space-y-1">
                        <p className="truncate text-sm text-foreground">{entry.theme.emoji} {entry.title}</p>
                        <p className="text-xs text-muted-foreground">{entry.cadence}</p>
                      </div>
                      <div className="shrink-0 text-right text-xs text-muted-foreground">
                        <div>{entry.startLabel} → {entry.endLabel}</div>
                        <div>{entry.durationMinutes} min{entry.overlapRisk ? " · overlap risk" : ""}</div>
                      </div>
                    </div>
                  ))}
                </div>
              </>
            ) : (
              <div className="rounded-[22px] border border-white/8 bg-white/[0.035] px-4 py-4 text-sm text-muted-foreground">
                Daily timeline unavailable for these cron expressions — this overview only maps recurring daily hour/minute schedules.
              </div>
            )}
          </CardContent>
        </Card>

        {jobs.length === 0 && (
          <Card className="rounded-[26px] border-border/70 bg-card/80">
            <CardContent className="py-8 text-center text-sm text-muted-foreground">
              {t.cron.noJobs}
            </CardContent>
          </Card>
        )}

        {jobs.map((job) => {
          const theme = getJobTheme(job);
          const title = job.name || truncatePrompt(job.prompt, 72);
          const promptPreview = truncatePrompt(job.prompt);
          const cadence = describeDailyCadence(job);
          const duration = estimateDurationMinutes(job);
          const slots = getDailyRunSlots(job);
          const primaryRunWindow = slots.length ? `${formatMinuteOfDay(slots[0])}${slots.length > 1 ? ` +${slots.length - 1}` : ""}` : null;
          const isEditing = editingJobId === job.id;
          const draft = editDrafts[job.id] || makeDraft(job);
          const scheduleBuilder = parseScheduleBuilderState(draft.schedule);

          return (
            <Card key={job.id} className={cn("cron-job-card overflow-visible rounded-[30px] shadow-none", theme.cardClass)}>
              <CardContent className="flex flex-col gap-5 p-5 lg:flex-row lg:items-start lg:gap-6">
                <div className={cn("flex h-14 w-14 shrink-0 items-center justify-center rounded-[20px] border text-2xl", theme.bubbleClass)}>
                  <span aria-hidden="true">{theme.emoji}</span>
                </div>

                <div className="min-w-0 flex-1 space-y-3">
                  <div className="flex flex-col gap-3 xl:flex-row xl:items-start xl:justify-between">
                    <div className="min-w-0 space-y-2">
                      <div className="cron-title-group flex flex-wrap items-center gap-2.5">
                        <h3 className="truncate text-base font-semibold text-foreground">{title}</h3>
                        <Badge className={theme.statusBadgeClass} variant="outline">⏱️ {job.state}</Badge>
                        <Badge className={theme.accentBadgeClass} variant="outline">{theme.emoji} {theme.label}</Badge>
                        {job.deliver && job.deliver !== "local" && (
                          <Badge className={theme.subtleBadgeClass} variant="outline">📬 {job.deliver}</Badge>
                        )}
                      </div>
                      {!isEditing && (
                        <p className="max-w-4xl text-sm text-muted-foreground">{promptPreview}</p>
                      )}
                    </div>

                    <div className="cron-action-cluster flex shrink-0 items-center gap-2 self-start">
                      {isEditing ? (
                        <>
                          <Button
                            variant="ghost"
                            size="icon"
                            className={cn("rounded-full border", theme.actionButtonClass)}
                            title="Save changes"
                            aria-label="Save changes"
                            onClick={() => handleSaveEdit(job)}
                            disabled={savingJobId === job.id}
                          >
                            <Save className="h-4 w-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon"
                            className={cn("rounded-full border", theme.actionButtonClass)}
                            title="Cancel edit"
                            aria-label="Cancel edit"
                            onClick={() => handleCancelEdit(job)}
                          >
                            <X className="h-4 w-4" />
                          </Button>
                        </>
                      ) : (
                        <Button
                          variant="ghost"
                          size="icon"
                          className={cn("cron-edit-button rounded-full border", theme.actionButtonClass)}
                          title="Edit cron"
                          aria-label="Edit cron"
                          onClick={() => handleStartEdit(job)}
                        >
                          <Pencil className="h-4 w-4" />
                        </Button>
                      )}

                      <Button
                        variant="ghost"
                        size="icon"
                        className={cn("rounded-full border", theme.actionButtonClass)}
                        title={job.state === "paused" ? t.cron.resume : t.cron.pause}
                        aria-label={job.state === "paused" ? t.cron.resume : t.cron.pause}
                        onClick={() => handlePauseResume(job)}
                      >
                        {job.state === "paused" ? <Play className="h-4 w-4" /> : <Pause className="h-4 w-4" />}
                      </Button>

                      <Button
                        variant="ghost"
                        size="icon"
                        className={cn("rounded-full border", theme.actionButtonClass)}
                        title={t.cron.triggerNow}
                        aria-label={t.cron.triggerNow}
                        onClick={() => handleTrigger(job)}
                      >
                        <Zap className="h-4 w-4" />
                      </Button>

                      <Button
                        variant="ghost"
                        size="icon"
                        className={cn("rounded-full border", theme.actionButtonClass)}
                        title={t.common.delete}
                        aria-label={t.common.delete}
                        onClick={() => handleDelete(job)}
                      >
                        <Trash2 className="h-4 w-4 text-destructive" />
                      </Button>
                    </div>
                  </div>

                  {isEditing && (
                    <div className="cron-edit-panel grid gap-4 rounded-[22px] border border-white/10 bg-white/[0.04] p-4">
                      <div className="grid gap-2 md:grid-cols-2">
                        <div className="grid gap-2">
                          <Label htmlFor={`job-name-${job.id}`}>Job name</Label>
                          <Input
                            id={`job-name-${job.id}`}
                            value={draft.name}
                            onChange={(e) => handleDraftChange(job.id, "name", e.target.value)}
                            placeholder="Friendly title"
                            className="border-white/12 bg-white/[0.04]"
                          />
                        </div>
                        <div className="cron-schedule-builder grid gap-3 rounded-[18px] border border-white/8 bg-white/[0.03] p-3">
                          <div className="grid gap-2 md:grid-cols-2">
                            <div className="grid gap-2">
                              <Label>Run pattern</Label>
                              <Select
                                value={scheduleBuilder.pattern}
                                onValueChange={(value) => handleScheduleBuilderChange(job.id, "pattern", value)}
                                className="cron-preset-pill cron-preset-pill-emerald"
                              >
                                <SelectOption value="once">Once per day</SelectOption>
                                <SelectOption value="twice">Twice per day</SelectOption>
                                <SelectOption value="three">3 times per day</SelectOption>
                                <SelectOption value="custom">Custom expression</SelectOption>
                              </Select>
                            </div>
                            <div className="grid gap-2">
                              <Label>First run</Label>
                              <div className="grid grid-cols-2 gap-2">
                                <Select
                                  value={scheduleBuilder.firstHour}
                                  onValueChange={(value) => handleScheduleBuilderChange(job.id, "firstHour", value)}
                                  className="cron-preset-pill cron-preset-pill-emerald"
                                >
                                  {hourOptions.map((hour) => (
                                    <SelectOption key={`h1-${job.id}-${hour}`} value={hour}>{hour}</SelectOption>
                                  ))}
                                </Select>
                                <Select
                                  value={scheduleBuilder.firstMinute}
                                  onValueChange={(value) => handleScheduleBuilderChange(job.id, "firstMinute", value)}
                                  className="cron-preset-pill cron-preset-pill-emerald"
                                >
                                  {minuteOptions.map((minute) => (
                                    <SelectOption key={`m1-${job.id}-${minute}`} value={minute}>{minute}</SelectOption>
                                  ))}
                                </Select>
                              </div>
                            </div>
                          </div>

                          {scheduleBuilder.pattern !== "once" && scheduleBuilder.pattern !== "custom" && (
                            <div className="grid gap-2 md:grid-cols-2">
                              <div className="grid gap-2">
                                <Label>Second run</Label>
                                <div className="grid grid-cols-2 gap-2">
                                  <Select
                                    value={scheduleBuilder.secondHour}
                                    onValueChange={(value) => handleScheduleBuilderChange(job.id, "secondHour", value)}
                                    className="cron-preset-pill cron-preset-pill-emerald"
                                  >
                                    {hourOptions.map((hour) => (
                                      <SelectOption key={`h2-${job.id}-${hour}`} value={hour}>{hour}</SelectOption>
                                    ))}
                                  </Select>
                                  <div className="flex items-center rounded-full border border-white/10 bg-white/[0.04] px-3 text-xs text-muted-foreground">
                                    Same minute as first run
                                  </div>
                                </div>
                              </div>

                              {scheduleBuilder.pattern === "three" && (
                                <div className="grid gap-2">
                                  <Label>Third run</Label>
                                  <div className="grid grid-cols-2 gap-2">
                                    <Select
                                      value={scheduleBuilder.thirdHour}
                                      onValueChange={(value) => handleScheduleBuilderChange(job.id, "thirdHour", value)}
                                      className="cron-preset-pill cron-preset-pill-emerald"
                                    >
                                      {hourOptions.map((hour) => (
                                        <SelectOption key={`h3-${job.id}-${hour}`} value={hour}>{hour}</SelectOption>
                                      ))}
                                    </Select>
                                    <div className="flex items-center rounded-full border border-white/10 bg-white/[0.04] px-3 text-xs text-muted-foreground">
                                      Same minute as first run
                                    </div>
                                  </div>
                                </div>
                              )}
                            </div>
                          )}

                          <div className="grid gap-2">
                            <Label htmlFor={`job-schedule-${job.id}`}>Run time / cron expression</Label>
                            <Input
                              id={`job-schedule-${job.id}`}
                              value={draft.schedule}
                              onChange={(e) => handleDraftChange(job.id, "schedule", e.target.value)}
                              placeholder="0 13 * * * or every 6h"
                              className="border-white/12 bg-white/[0.04]"
                            />
                            <p className="text-xs text-muted-foreground">Use the builder above for normal daily timing, or switch to custom expression for advanced cron syntax.</p>
                          </div>
                        </div>
                      </div>
                      <div className="grid gap-2">
                        <Label htmlFor={`job-prompt-${job.id}`}>Description / prompt</Label>
                        <textarea
                          id={`job-prompt-${job.id}`}
                          value={draft.prompt}
                          onChange={(e) => handleDraftChange(job.id, "prompt", e.target.value)}
                          className="min-h-[120px] w-full rounded-[18px] border border-white/12 bg-white/[0.04] px-3 py-3 text-sm text-foreground outline-none focus:ring-1 focus:ring-foreground/20"
                          placeholder="What should this cron do on each run?"
                        />
                      </div>
                    </div>
                  )}

                  <div className="flex flex-wrap gap-2 text-[0.72rem] text-slate-950/70">
                    <span className="cron-meta-chip cron-meta-chip-pastel">🗓️ {job.schedule_display}</span>
                    <span className="cron-meta-chip cron-meta-chip-pastel">{cadence}</span>
                    <span className="cron-meta-chip cron-meta-chip-pastel">≈{duration} min/run</span>
                    {primaryRunWindow && (
                      <span className="cron-meta-chip cron-meta-chip-pastel">Starts {primaryRunWindow}</span>
                    )}
                    <span className="cron-meta-chip cron-meta-chip-pastel">Last: {formatTime(job.last_run_at)}</span>
                    <span className="cron-meta-chip cron-meta-chip-pastel">Next: {formatTime(job.next_run_at)}</span>
                  </div>

                  <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
                    <div className="min-w-[220px] max-w-sm">
                      <Select
                        value={job.agent_name || "default"}
                        onValueChange={(value) => handleReassignAgent(job, value)}
                        className={cn("cron-agent-select cron-preset-pill z-[260]", theme.pillClass)}
                      >
                        {presetOptions.map((preset) => (
                          <SelectOption key={`${job.id}-${preset.slug}`} value={preset.slug}>{preset.emoji || "🤖"} {preset.name}</SelectOption>
                        ))}
                      </Select>
                    </div>
                    <div className="text-[0.72rem] uppercase tracking-[0.16em] text-muted-foreground/70">
                      Job ID · {job.id}
                    </div>
                  </div>

                  {job.last_error && (
                    <p className="rounded-[18px] border border-destructive/25 bg-destructive/10 px-3 py-2 text-xs text-destructive">
                      {job.last_error}
                    </p>
                  )}
                </div>
              </CardContent>
            </Card>
          );
        })}

        {overlapCount > 0 && (
          <div className="flex items-center gap-2 rounded-[18px] border border-amber-200/18 bg-amber-50/[0.08] px-3 py-2 text-xs text-amber-50/90">
            <AlertTriangle className="h-4 w-4" />
            {overlapCount} overlap risk window{overlapCount === 1 ? "" : "s"} detected — consider shifting one cron by 15–20 minutes.
          </div>
        )}
      </div>
    </div>
  );
}
