import assert from 'node:assert/strict'
import test from 'node:test'

import {
  buildReviewerDecisionPayload,
  hasRecordedReviewerDecision,
  pendingReviewerFindings,
  requiresReviewerDecision,
  REVIEW_ACTIONS,
  reviewerStateLabel,
} from './reviewWorkflow.js'

test('only flagged, missing, and unresolved findings need a decision', () => {
  for (const status of ['flagged', 'missing', 'unresolved']) {
    assert.equal(requiresReviewerDecision({ status }), true)
  }
  for (const status of ['pass', 'not_applicable']) {
    assert.equal(requiresReviewerDecision({ status }), false)
  }
})

test('API review requirement is authoritative when present', () => {
  assert.equal(requiresReviewerDecision({ status: 'flagged', requires_reviewer_decision: false }), false)
  assert.equal(requiresReviewerDecision({ status: 'pass', requires_reviewer_decision: true }), true)
})

test('pending count excludes informational checks and includes missing timestamps', () => {
  const findings = [
    { status: 'pass' },
    { status: 'not_applicable' },
    { status: 'flagged' },
    { status: 'unresolved', reviewer_decision: 'verified' },
    { status: 'missing', reviewer_decision: 'requested_resubmission', reviewed_at: '2026-10-28T10:00:00Z' },
  ]
  assert.deepEqual(pendingReviewerFindings(findings).map((finding) => finding.status), ['flagged', 'unresolved'])
})

test('a recorded decision is complete only when it has an audit timestamp', () => {
  assert.equal(hasRecordedReviewerDecision({ reviewer_decision: 'verified', reviewed_at: '2026-10-28T10:00:00Z' }), true)
  assert.equal(hasRecordedReviewerDecision({ reviewer_decision: 'verified' }), false)
  assert.equal(hasRecordedReviewerDecision({ reviewer_decision: 'unknown', reviewed_at: '2026-10-28T10:00:00Z' }), false)
})

test('verified decisions need no irrelevant follow-up details', () => {
  assert.deepEqual(buildReviewerDecisionPayload('verified'), { reviewer_decision: 'verified' })
})

test('resubmission and escalation require details and keep action-specific state', () => {
  assert.equal(REVIEW_ACTIONS.requested_resubmission.fieldLabel, 'Information or correction required')
  assert.equal(REVIEW_ACTIONS.escalated.fieldLabel, 'Escalation reason and review requested')
  assert.throws(() => buildReviewerDecisionPayload('requested_resubmission', '  '), /required/)
  assert.throws(() => buildReviewerDecisionPayload('escalated', ''), /required/)
  assert.deepEqual(buildReviewerDecisionPayload('requested_resubmission', ' Upload a current certificate. '), {
    reviewer_decision: 'requested_resubmission',
    reviewer_notes: 'Upload a current certificate.',
  })
  assert.deepEqual(buildReviewerDecisionPayload('escalated', 'Refer to regional authority.'), {
    reviewer_decision: 'escalated',
    reviewer_notes: 'Refer to regional authority.',
  })
})

test('review states distinguish pending, verified, resubmission, and escalation', () => {
  assert.equal(reviewerStateLabel({ status: 'flagged' }), 'Needs reviewer action')
  assert.equal(reviewerStateLabel({ status: 'flagged', reviewer_decision: 'verified', reviewed_at: 'now' }), 'Verified')
  assert.equal(reviewerStateLabel({ status: 'missing', reviewer_decision: 'requested_resubmission', reviewed_at: 'now' }), 'Awaiting institution resubmission')
  assert.equal(reviewerStateLabel({ status: 'unresolved', reviewer_decision: 'escalated', reviewed_at: 'now' }), 'Escalated for further review')
  assert.equal(reviewerStateLabel({ status: 'pass' }), 'No reviewer decision needed')
})
