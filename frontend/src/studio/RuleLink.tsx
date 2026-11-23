import type { ReactNode } from 'react'

import { RULE_ID, useRuleHref } from './rules'

/** A rule id that opens its section of the manual in a new tab (QA 2026-11-23, item 20). */
export function RuleLink({ rule, children }: { rule: string; children?: ReactNode }) {
  const href = useRuleHref()(rule)
  if (!href) return <>{children ?? rule}</>
  return (
    <a href={href} target="_blank" rel="noreferrer" className="underline decoration-dotted underline-offset-2 hover:decoration-solid">
      {children ?? rule}
    </a>
  )
}

/** Text with every rule id ("GB-01") turned into a link to the manual. */
export function WithRuleLinks({ text }: { text: string }) {
  return (
    <>
      {text.split(RULE_ID).map((part, i) => (i % 2 === 1 ? <RuleLink key={i} rule={part} /> : part))}
    </>
  )
}
