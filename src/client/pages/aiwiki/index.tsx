import { useCallback, useEffect, useMemo, useState } from 'react'
import { App, Col, Row, theme } from 'antd'
import type { UploadFile, UploadProps } from 'antd'
import { useAuth } from '../../hooks/useAuth'
import { createAiwikiJob, getAiwikiJob, getAiwikiResult, listAiwikiJobs, type AiwikiJob, type AiwikiJobSummary, type AiwikiResult } from '../../lib/aiwiki'
import { resolveErrorMessage } from '../dashboard/ExamplePage/utils'
import { ACTIVE_STATUSES, ACCEPTED_TYPES, entryTypeLabel, statusMeta } from './helpers'
import KeywordModal from './KeywordModal'
import ResultView from './ResultView'
import { HistorySidebar, TaskSidebar } from './sidebars'
import UploadPanel from './UploadPanel'

export default function AiwikiPage() {
  const { message } = App.useApp()
  const { token } = theme.useToken()
  const { user } = useAuth()
  const [fileList, setFileList] = useState<UploadFile[]>([])
  const [job, setJob] = useState<AiwikiJob | null>(null)
  const [history, setHistory] = useState<AiwikiJobSummary[]>([])
  const [result, setResult] = useState<AiwikiResult | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [refreshing, setRefreshing] = useState(false)
  const [historyLoading, setHistoryLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [selectedTerms, setSelectedTerms] = useState<string[]>([])
  const [entryFilter, setEntryFilter] = useState<string>('全部')
  const [activeEntrySlug, setActiveEntrySlug] = useState<string | null>(null)
  const [keywordModalOpen, setKeywordModalOpen] = useState(false)
  const [keywordSearch, setKeywordSearch] = useState('')

  const isAdmin = user?.role === 'admin'
  const meta = statusMeta(job?.status)

  const files = useMemo(
    () => fileList.map((item) => item.originFileObj).filter(Boolean) as File[],
    [fileList],
  )

  const uploadProps: UploadProps = {
    multiple: true,
    accept: ACCEPTED_TYPES,
    fileList,
    beforeUpload: () => false,
    onChange: ({ fileList: nextList }) => {
      setFileList(nextList.slice(0, 10))
      setError(null)
    },
    onRemove: (file) => {
      setFileList((current) => current.filter((item) => item.uid !== file.uid))
    },
  }

  const loadHistory = useCallback(async () => {
    setHistoryLoading(true)
    try {
      const list = await listAiwikiJobs({ limit: 50, offset: 0 })
      setHistory(list.items)
    } catch (err) {
      setError(resolveErrorMessage(err))
    } finally {
      setHistoryLoading(false)
    }
  }, [])

  const refreshJob = useCallback(async (jobId: string, silent = false) => {
    if (!silent) setRefreshing(true)
    try {
      const latest = await getAiwikiJob(jobId)
      setJob(latest)
      setError(null)
      if (latest.status === 'completed') {
        setResult(await getAiwikiResult(jobId))
        void loadHistory()
      } else if (latest.status === 'failed') {
        setResult(null)
        void loadHistory()
      }
    } catch (err) {
      const text = resolveErrorMessage(err)
      setError(text)
      if (!silent) message.error(text)
    } finally {
      if (!silent) setRefreshing(false)
    }
  }, [loadHistory, message])

  const selectHistoryJob = useCallback(async (jobId: string) => {
    setRefreshing(true)
    setError(null)
    setResult(null)
    setSelectedTerms([])
    setActiveEntrySlug(null)
    try {
      const latest = await getAiwikiJob(jobId)
      setJob(latest)
      if (latest.status === 'completed') {
        setResult(await getAiwikiResult(jobId))
      }
    } catch (err) {
      const text = resolveErrorMessage(err)
      setError(text)
      message.error(text)
    } finally {
      setRefreshing(false)
    }
  }, [message])

  useEffect(() => {
    void loadHistory()
  }, [loadHistory])

  useEffect(() => {
    if (!job?.id || !ACTIVE_STATUSES.has(job.status)) return
    const timer = window.setInterval(() => {
      void refreshJob(job.id, true)
    }, 2000)
    return () => window.clearInterval(timer)
  }, [job?.id, job?.status, refreshJob])

  const handleSubmit = async () => {
    if (!files.length) {
      setError('请先选择文件')
      return
    }
    setSubmitting(true)
    setError(null)
    setResult(null)
    setSelectedTerms([])
    setActiveEntrySlug(null)
    try {
      const created = await createAiwikiJob(files)
      setJob(created)
      message.success('任务已提交')
      void loadHistory()
      void refreshJob(created.id, true)
    } catch (err) {
      const text = resolveErrorMessage(err)
      setError(text)
      message.error(text)
    } finally {
      setSubmitting(false)
    }
  }

  const entriesBySlug = useMemo(() => {
    return new Map((result?.wiki_entries ?? []).map((entry) => [entry.slug, entry]))
  }, [result?.wiki_entries])

  const activeEntry = useMemo(() => {
    if (!activeEntrySlug) return null
    return entriesBySlug.get(activeEntrySlug) ?? null
  }, [activeEntrySlug, entriesBySlug])

  const availableTerms = useMemo(() => result?.highlight_terms ?? [], [result])

  const filteredEntries = useMemo(() => {
    if (!result) return []
    return entryFilter === '全部'
      ? result.wiki_entries
      : result.wiki_entries.filter((entry) => entryTypeLabel(entry.type) === entryFilter)
  }, [entryFilter, result])

  useEffect(() => {
    setSelectedTerms([])
  }, [availableTerms])

  return (
    <>
      <Row gutter={[16, 16]} align="stretch">
        <Col xs={24} xl={5}>
          <HistorySidebar
            history={history}
            activeJobId={job?.id}
            loading={historyLoading}
            isAdmin={isAdmin}
            onRefresh={loadHistory}
            onSelect={selectHistoryJob}
          />
        </Col>
        <Col xs={24} xl={13}>
          {result ? (
            <ResultView
              result={result}
              selectedTerms={selectedTerms}
              entryFilter={entryFilter}
              filteredEntries={filteredEntries}
              entriesBySlug={entriesBySlug}
              activeEntry={activeEntry}
              onOpenKeywordModal={() => setKeywordModalOpen(true)}
              onEntryFilterChange={setEntryFilter}
              onOpenEntry={setActiveEntrySlug}
              onCloseEntry={() => setActiveEntrySlug(null)}
            />
          ) : (
            <UploadPanel
              error={error}
              job={job}
              meta={meta}
              submitting={submitting}
              token={token}
              uploadProps={uploadProps}
              onSubmit={handleSubmit}
            />
          )}
        </Col>
        <Col xs={24} xl={6}>
          <TaskSidebar
            job={job}
            result={result}
            meta={meta}
            refreshing={refreshing}
            onRefresh={() => job && void refreshJob(job.id)}
          />
        </Col>
      </Row>

      <KeywordModal
        open={keywordModalOpen}
        terms={availableTerms}
        selectedTerms={selectedTerms}
        keywordSearch={keywordSearch}
        onSearch={setKeywordSearch}
        onApply={(terms) => {
          setSelectedTerms(terms)
          setKeywordModalOpen(false)
        }}
        onClose={() => setKeywordModalOpen(false)}
      />
    </>
  )
}
