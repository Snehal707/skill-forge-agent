import React from "react";

type StatsBarProps = {
  totalSkills: number;
  skillsToday: number;
  successRate: number;
  domainsCovered: number;
};

export default function StatsBar({
  totalSkills,
  skillsToday,
  successRate,
  domainsCovered,
}: StatsBarProps) {
  const items = [
    { label: "Total Skills Learned", value: totalSkills },
    { label: "Skills Today", value: skillsToday },
    { label: "Validation Success Rate (%)", value: successRate },
    { label: "Domains Covered", value: domainsCovered },
  ];

  return (
    <section className="grid grid-cols-2 gap-4 md:grid-cols-4">
      {items.map((item) => (
        <div
          key={item.label}
          className="rounded-lg border border-border bg-surface p-4"
        >
          <div className="text-xs uppercase tracking-wide text-muted">
            {item.label}
          </div>
          <div className="mt-2 text-2xl font-semibold text-text">
            {item.value}
          </div>
        </div>
      ))}
    </section>
  );
}

