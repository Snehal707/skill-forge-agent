import React from "react";
import ReactMarkdown from "react-markdown";
import rehypeHighlight from "rehype-highlight";

type SkillDetail = {
  id: string;
  name: string;
  domain: string;
  category: string;
  validationPassed: boolean;
  createdAt: string;
  content: string;
  sourcesCount?: number;
  attempts?: number;
};

type SkillModalProps = {
  open: boolean;
  onClose: () => void;
  skill: SkillDetail | null;
};

export default function SkillModal({ open, onClose, skill }: SkillModalProps) {
  if (!open || !skill) return null;

  return (
    <div className="fixed inset-0 z-40 flex justify-end bg-black/60">
      <div className="h-full w-full max-w-xl border-l border-border bg-surface p-6">
        <header className="mb-4 flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-text">{skill.name}</h2>
            <div className="mt-1 flex flex-wrap gap-2 text-xs text-muted">
              <span className="rounded-full border border-border px-2 py-0.5">
                {skill.domain}
              </span>
              <span className="rounded-full border border-border px-2 py-0.5">
                {skill.category}
              </span>
              <span
                className={`rounded-full px-2 py-0.5 text-xs ${
                  skill.validationPassed
                    ? "bg-green/10 text-green"
                    : "bg-yellow/10 text-yellow"
                }`}
              >
                {skill.validationPassed ? "Validated" : "Needs Validation"}
              </span>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded border border-border px-3 py-1 text-xs text-muted hover:border-blue hover:text-blue"
          >
            Close
          </button>
        </header>

        <section className="prose prose-invert max-w-none overflow-y-auto border-y border-border py-4 text-sm">
          <ReactMarkdown rehypePlugins={[rehypeHighlight]}>
            {skill.content}
          </ReactMarkdown>
        </section>

        <footer className="mt-4 flex items-center justify-between text-xs text-muted">
          <div className="space-x-2">
            {typeof skill.sourcesCount === "number" && (
              <span>Sources: {skill.sourcesCount}</span>
            )}
            {typeof skill.attempts === "number" && (
              <span>Attempts: {skill.attempts}</span>
            )}
            <span>
              Saved: {new Date(skill.createdAt).toLocaleString()}
            </span>
          </div>
          <button
            type="button"
            className="rounded border border-border px-3 py-1 text-xs text-blue hover:border-blue"
            onClick={() => {
              if (navigator.clipboard && skill.content) {
                navigator.clipboard.writeText(skill.content).catch(() => {});
              }
            }}
          >
            Copy SKILL.md
          </button>
        </footer>
      </div>
    </div>
  );
}

