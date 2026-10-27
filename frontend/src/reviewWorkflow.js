const REVIEW_REQUIRED_STATUSES = new Set(['flagged', 'missing', 'unresolved'])
const VALID_REVIEW_DECISIONS = new Set(['verified', 'confirmed_discrepancy', 'requested_resubmission', 'escalated'])

export const REVIEW_ACTIONS = {
  requested_resubmission: {
    title: 'Request information from the institution',
    description: 'State the document, correction, or clarification the institution must provide.',
    fieldLabel: 'Information or correction required',
    placeholder: 'For example: Upload a current Fire Safety Certificate showing the institution address.',
    submitLabel: 'Send resubmission request',
    successLabel: 'Resubmission request recorded',
  },
  escalated: {
    title: 'Escalate for further review',
    description: 'Explain why this finding needs another reviewer or authority to assess it.',
    fieldLabel: 'Escalation reason and review requested',
    placeholder: 'Describe the issue and name the additional review or authority needed, if known.',
    submitLabel: 'Record escalation',
    successLabel: 'Escalation recorded',
  },
}

export function requiresReviewerDecision(finding) {
  if (typeof finding?.requires_reviewer_decision === 'boolean') {
    return finding.requires_reviewer_decision
  }
  return REVIEW_REQUIRED_STATUSES.has(finding?.status)
}

export function hasRecordedReviewerDecision(finding) {
  return VALID_REVIEW_DECISIONS.has(finding?.reviewer_decision) && Boolean(finding?.reviewed_at)
}

export function pendingReviewerFindings(findings = []) {
  return findings.filter((finding) =>
    requiresReviewerDecision(finding) && !hasRecordedReviewerDecision(finding),
  )
}

export function buildReviewerDecisionPayload(decision, details = '') {
  if (decision === 'verified' || decision === 'confirmed_discrepancy') {
    return { reviewer_decision: decision }
  }
  if (!REVIEW_ACTIONS[decision]) throw new Error('Choose a supported reviewer action.')

  const reviewerNotes = details.trim()
  if (!reviewerNotes) throw new Error(REVIEW_ACTIONS[decision].fieldLabel + ' is required.')
  return { reviewer_decision: decision, reviewer_notes: reviewerNotes }
}

export function reviewerStateLabel(finding) {
  if (!requiresReviewerDecision(finding)) return 'No reviewer decision needed'
  if (!hasRecordedReviewerDecision(finding)) return 'Needs reviewer action'
  if (finding.reviewer_decision === 'verified') return 'Verified'
  if (finding.reviewer_decision === 'requested_resubmission') return 'Awaiting institution resubmission'
  if (finding.reviewer_decision === 'escalated') return 'Escalated for further review'
  if (finding.reviewer_decision === 'confirmed_discrepancy') return 'Discrepancy confirmed'
  return 'Needs reviewer action'
}
