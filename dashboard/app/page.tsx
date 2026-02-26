"use client";

import { useEffect, useMemo, useState } from "react";

import LiveFeed from "../components/LiveFeed";
import SkillCard from "../components/SkillCard";
import SkillModal from "../components/SkillModal";
import StatsBar from "../components/StatsBar";
import { supabase, type EventRow, type SkillRow } from "../lib/supabase";

type LiveEvent = {
  id: string;
  createdAt: string;
  eventType: string;
  message: string;
};

type SkillItem = {
  id: string;
  name: string;
  domain: string;
  category: string;
  validationPassed: boolean;
  createdAt: string;
  description?: string | null;
  content?: string;
  sourcesCount?: number;
  attempts?: number;
};

export default function Page() {
  const [events, setEvents] = useState<LiveEvent[]>([]);
  const [skills, setSkills] = useState<SkillItem[]>([]);
  const [selectedSkill, setSelectedSkill] = useState<SkillItem | null>(null);
  const [domainFilter, setDomainFilter] = useState<string>("all");
  const [categoryFilter, setCategoryFilter] = useState<string>("all");

  useEffect(() => {
    const loadInitial = async () => {
      if (!supabase) return;
      const client = supabase;
      const [{ data: eventsData }, { data: skillsData }] = await Promise.all([
        client
          .from("events")
          .select("id, event_type, domain, skill_name, message, metadata, created_at")
          .order("created_at", { ascending: false })
          .limit(50),
        client
          .from("skills")
          .select(
            "id, name, domain, category, description, content, validation_passed, sources_count, attempts, created_at",
          )
          .order("created_at", { ascending: false }),
      ]);

      setEvents(
        (eventsData as EventRow[] | null | undefined)?.map((e) => ({
          id: e.id,
          createdAt: e.created_at,
          eventType: e.event_type,
          message: e.message,
        })) ?? [],
      );

      setSkills(
        (skillsData as SkillRow[] | null | undefined)?.map((s) => ({
          id: s.id,
          name: s.name,
          domain: s.domain,
          category: s.category,
          validationPassed: s.validation_passed,
          createdAt: s.created_at,
          description: s.description,
          content: s.content,
          sourcesCount: s.sources_count ?? undefined,
          attempts: s.attempts ?? undefined,
        })) ?? [],
      );
    };

    void loadInitial();

    if (!supabase) {
      return;
    }
    const client = supabase;
    const channel = client
      .channel("skill-forge-dashboard")
      .on(
        "postgres_changes",
        { event: "*", schema: "public", table: "events" },
        (payload) => {
          const row = payload.new as EventRow;
          setEvents((prev) => [
            {
              id: row.id,
              createdAt: row.created_at,
              eventType: row.event_type,
              message: row.message,
            },
            ...prev,
          ].slice(0, 50));
        },
      )
      .on(
        "postgres_changes",
        { event: "*", schema: "public", table: "skills" },
        (payload) => {
          const row = payload.new as SkillRow;
          setSkills((prev) => {
            const updated: SkillItem = {
              id: row.id,
              name: row.name,
              domain: row.domain,
              category: row.category,
              validationPassed: row.validation_passed,
              createdAt: row.created_at,
              description: row.description,
              content: row.content,
              sourcesCount: row.sources_count ?? undefined,
              attempts: row.attempts ?? undefined,
            };
            const others = prev.filter((s) => s.id !== row.id);
            return [updated, ...others];
          });
        },
      )
      .subscribe();

    return () => {
      client.removeChannel(channel);
    };
  }, []);

  // Dedupe by name (keep latest) so list matches Hermes disk
  const uniqueSkills = useMemo(() => {
    const byName = new Map<string, SkillItem>();
    for (const s of skills) {
      const existing = byName.get(s.name);
      if (!existing || (s.createdAt ?? "") > (existing.createdAt ?? "")) {
        byName.set(s.name, s);
      }
    }
    return Array.from(byName.values());
  }, [skills]);

  const domains = useMemo(
    () => Array.from(new Set(uniqueSkills.map((s) => s.domain))).sort(),
    [uniqueSkills],
  );
  const categories = useMemo(
    () => Array.from(new Set(uniqueSkills.map((s) => s.category))).sort(),
    [uniqueSkills],
  );

  const filteredSkills = uniqueSkills.filter((s) => {
    if (domainFilter !== "all" && s.domain !== domainFilter) return false;
    if (categoryFilter !== "all" && s.category !== categoryFilter) return false;
    return true;
  });

  const stats = useMemo(() => {
    const total = uniqueSkills.length;
    const now = new Date();
    const todayIso = new Date(
      Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate()),
    ).toISOString();
    const skillsToday = uniqueSkills.filter(
      (s) => (s.createdAt ?? "") >= todayIso,
    ).length;
    const validated = uniqueSkills.filter((s) => s.validationPassed).length;
    const successRate = total > 0 ? (validated / total) * 100 : 0;
    const domainsCovered = domains.length;
    return { total, skillsToday, successRate, domainsCovered };
  }, [uniqueSkills, domains]);

  return (
    <main className="flex-1 space-y-6 p-6">
      <StatsBar
        totalSkills={stats.total}
        skillsToday={stats.skillsToday}
        successRate={Number(stats.successRate.toFixed(1))}
        domainsCovered={stats.domainsCovered}
      />
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[2fr,3fr]">
        <LiveFeed events={events} />
        <section className="space-y-4">
          <header className="flex flex-wrap items-center justify-between gap-3">
            <h2 className="text-lg font-semibold text-text">Skills</h2>
            <div className="flex flex-wrap gap-2 text-xs">
              <select
                className="rounded border border-border bg-surface px-2 py-1 text-xs text-text"
                value={domainFilter}
                onChange={(e) => setDomainFilter(e.target.value)}
              >
                <option value="all">All domains</option>
                {domains.map((d) => (
                  <option key={d} value={d}>
                    {d}
                  </option>
                ))}
              </select>
              <select
                className="rounded border border-border bg-surface px-2 py-1 text-xs text-text"
                value={categoryFilter}
                onChange={(e) => setCategoryFilter(e.target.value)}
              >
                <option value="all">All categories</option>
                {categories.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
            </div>
          </header>
          <div className="grid grid-cols-1 gap-4">
            {filteredSkills.map((skill) => (
              <SkillCard
                key={skill.name}
                skill={skill}
                onClick={() => setSelectedSkill(skill)}
              />
            ))}
            {filteredSkills.length === 0 && (
              <div className="rounded border border-border bg-surface p-4 text-sm text-muted">
                No skills match the current filters yet.
              </div>
            )}
          </div>
        </section>
      </div>
      <SkillModal
        open={!!selectedSkill}
        onClose={() => setSelectedSkill(null)}
        skill={
          selectedSkill
            ? {
                id: selectedSkill.id,
                name: selectedSkill.name,
                domain: selectedSkill.domain,
                category: selectedSkill.category,
                validationPassed: selectedSkill.validationPassed,
                createdAt: selectedSkill.createdAt,
                content: selectedSkill.content ?? "",
                sourcesCount: selectedSkill.sourcesCount,
                attempts: selectedSkill.attempts,
              }
            : null
        }
      />
    </main>
  );
}

