import React from "react";

type Skill = {
  id: string;
  name: string;
  domain: string;
  category: string;
  validationPassed: boolean;
  createdAt: string;
};

type SkillCardProps = {
  skill: Skill;
  onClick?: () => void;
};

function timeAgo(iso: string): string {
  const date = new Date(iso);
  const diffMs = Date.now() - date.getTime();
  const diffSec = Math.floor(diffMs / 1000);
  const diffMin = Math.floor(diffSec / 60);
  const diffHours = Math.floor(diffMin / 60);
  const diffDays = Math.floor(diffHours / 24);

  if (diffDays > 0) return `${diffDays}d ago`;
  if (diffHours > 0) return `${diffHours}h ago`;
  if (diffMin > 0) return `${diffMin}m ago`;
  return "just now";
}

export default function SkillCard({ skill, onClick }: SkillCardProps) {
  return (
    <article
      className="cursor-pointer rounded-lg border border-border bg-surface p-4 transition hover:border-blue"
      onClick={onClick}
    >
      <header className="flex items-center justify-between">
        <h3 className="text-base font-semibold text-text">{skill.name}</h3>
        <span
          className={`rounded-full px-2 py-0.5 text-xs ${
            skill.validationPassed
              ? "bg-green/10 text-green"
              : "bg-yellow/10 text-yellow"
          }`}
        >
          {skill.validationPassed ? "Validated" : "Needs Validation"}
        </span>
      </header>
      <div className="mt-2 flex flex-wrap gap-2 text-xs text-muted">
        <span className="rounded-full border border-border px-2 py-0.5">
          {skill.domain}
        </span>
        <span className="rounded-full border border-border px-2 py-0.5">
          {skill.category}
        </span>
      </div>
      <footer className="mt-3 text-xs text-muted">{timeAgo(skill.createdAt)}</footer>
    </article>
  );
}
