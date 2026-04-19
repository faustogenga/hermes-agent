import { useEffect, useState } from "react";
import {
  Bot,
  Brain,
  Eye,
  FileText,
  Gauge,
  Shield,
  Sparkles,
  Wrench,
} from "lucide-react";
import { api } from "@/lib/api";
import type { AgentProfileResponse, AgentProfileSource } from "@/lib/api";
import { formatTokenCount } from "@/lib/format";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

function SourceCard({ source }: { source: AgentProfileSource }) {
  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <CardTitle className="text-base">{source.title}</CardTitle>
            <p className="mt-1 break-all font-mono-ui text-[11px] text-muted-foreground">
              {source.path}
            </p>
          </div>
          <Badge variant={source.present ? "success" : "outline"}>
            {source.present ? "Loaded" : "Missing"}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        <p className="text-sm text-muted-foreground">{source.summary}</p>
        {source.content ? (
          <pre className="overflow-x-auto whitespace-pre-wrap border border-border bg-muted/30 p-3 text-xs leading-5 text-foreground/90">
            {source.content}
          </pre>
        ) : (
          <div className="border border-dashed border-border p-3 text-xs text-muted-foreground">
            No content available.
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export default function AgentPage() {
  const [profile, setProfile] = useState<AgentProfileResponse | null>(null);

  useEffect(() => {
    api.getAgentProfile().then(setProfile).catch(() => setProfile(null));
  }, []);

  if (!profile) {
    return (
      <div className="flex items-center justify-center py-24">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      </div>
    );
  }

  const caps = profile.model.capabilities ?? {};

  return (
    <div className="flex flex-col gap-6">
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <Bot className="h-5 w-5 text-muted-foreground" />
            <CardTitle className="text-base">{profile.name}</CardTitle>
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
                  <Sparkles className="h-3.5 w-3.5" /> Personality
                </div>
                <div className="mt-2 text-sm font-medium">
                  {profile.active_personality || "default"}
                </div>
              </div>
              <div className="border border-border p-3">
                <div className="flex items-center gap-2 text-xs uppercase tracking-[0.14em] text-muted-foreground">
                  <Wrench className="h-3.5 w-3.5" /> Model
                </div>
                <div className="mt-2 text-sm font-medium break-all">
                  {profile.model.model || "unknown"}
                </div>
                <div className="mt-1 text-xs text-muted-foreground">
                  {profile.model.provider || "provider not set"}
                </div>
              </div>
              <div className="border border-border p-3">
                <div className="flex items-center gap-2 text-xs uppercase tracking-[0.14em] text-muted-foreground">
                  <Gauge className="h-3.5 w-3.5" /> Context window
                </div>
                <div className="mt-2 text-sm font-medium">
                  {profile.model.effective_context_length > 0
                    ? formatTokenCount(profile.model.effective_context_length)
                    : "unknown"}
                </div>
                {profile.model.config_context_length > 0 && (
                  <div className="mt-1 text-xs text-muted-foreground">
                    Override active · auto {formatTokenCount(profile.model.auto_context_length)}
                  </div>
                )}
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
                {!caps.supports_tools && !caps.supports_vision && !caps.supports_reasoning && !caps.model_family && (
                  <span className="text-xs text-muted-foreground">No capability metadata available.</span>
                )}
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-4 xl:grid-cols-2">
        {profile.sources.map((source) => (
          <SourceCard key={source.key} source={source} />
        ))}
      </div>

      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <FileText className="h-5 w-5 text-muted-foreground" />
            <CardTitle className="text-base">How this page is built</CardTitle>
          </div>
        </CardHeader>
        <CardContent className="text-sm leading-6 text-muted-foreground">
          This view summarizes the live agent identity from SOUL.md, project AGENTS.md,
          saved USER.md and MEMORY.md entries, plus the active runtime model and selected
          personality.
        </CardContent>
      </Card>
    </div>
  );
}
