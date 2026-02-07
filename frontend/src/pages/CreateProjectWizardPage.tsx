import { useMemo, useRef, useState, type ChangeEvent, type DragEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { Button, Checkbox, Input, Select, useToast } from '../components/ui'

type ProjectType = 'Greenfield' | 'Brownfield'
type GreenfieldTemplate = 'Starter SaaS' | 'Internal Ops' | 'Public Portal'
type GreenfieldDatabase = 'PostgreSQL' | 'MySQL' | 'SQLite'
type GitProvider = 'GitHub' | 'GitLab'
type ImportDepth = 'Full analysis' | 'Shallow scan'
type BrownfieldSourceMode = 'Repository' | 'Upload'

type GitRepository = {
  id: string
  provider: GitProvider
  name: string
  fullName: string
  url: string
  defaultBranch: string
  branches: string[]
  lastCommitAt: string
}

const brownfieldRepos: GitRepository[] = [
  {
    id: 'gh-1',
    provider: 'GitHub',
    name: 'assisted-living-ehr',
    fullName: 'specgen/assisted-living-ehr',
    url: 'https://github.com/specgen/assisted-living-ehr',
    defaultBranch: 'main',
    branches: ['main', 'develop', 'release/2026-q1'],
    lastCommitAt: '2026-02-06T10:12:00.000Z',
  },
  {
    id: 'gh-2',
    provider: 'GitHub',
    name: 'care-ops-dashboard',
    fullName: 'specgen/care-ops-dashboard',
    url: 'https://github.com/specgen/care-ops-dashboard',
    defaultBranch: 'main',
    branches: ['main', 'staging'],
    lastCommitAt: '2026-02-04T18:05:00.000Z',
  },
  {
    id: 'gl-1',
    provider: 'GitLab',
    name: 'resident-intake-service',
    fullName: 'health/resident-intake-service',
    url: 'https://gitlab.com/health/resident-intake-service',
    defaultBranch: 'master',
    branches: ['master', 'develop', 'hotfix/intake-validation'],
    lastCommitAt: '2026-02-05T09:22:00.000Z',
  },
  {
    id: 'gl-2',
    provider: 'GitLab',
    name: 'med-admin-automation',
    fullName: 'health/med-admin-automation',
    url: 'https://gitlab.com/health/med-admin-automation',
    defaultBranch: 'main',
    branches: ['main', 'qa'],
    lastCommitAt: '2026-02-01T16:40:00.000Z',
  },
]

const stepLabels = ['Basics', 'Configuration', 'Review']

export function CreateProjectWizardPage() {
  const navigate = useNavigate()
  const { pushToast } = useToast()
  const [step, setStep] = useState(0)
  const [projectName, setProjectName] = useState('')
  const [description, setDescription] = useState('')
  const [projectType, setProjectType] = useState<ProjectType>('Greenfield')
  const [targetStack, setTargetStack] = useState('React + FastAPI')
  const [template, setTemplate] = useState<GreenfieldTemplate>('Starter SaaS')
  const [database, setDatabase] = useState<GreenfieldDatabase>('PostgreSQL')
  const [includeAuth, setIncludeAuth] = useState(true)
  const [includeAuditLog, setIncludeAuditLog] = useState(true)
  const [includeNotifications, setIncludeNotifications] = useState(false)
  const [gitProvider, setGitProvider] = useState<GitProvider>('GitHub')
  const [githubConnected, setGithubConnected] = useState(false)
  const [githubConnecting, setGithubConnecting] = useState(false)
  const [githubAccount, setGithubAccount] = useState('')
  const [gitlabConnected, setGitlabConnected] = useState(false)
  const [gitlabConnecting, setGitlabConnecting] = useState(false)
  const [gitlabAccount, setGitlabAccount] = useState('')
  const [repoSearch, setRepoSearch] = useState('')
  const [selectedRepoId, setSelectedRepoId] = useState('')
  const [selectedBranch, setSelectedBranch] = useState('')
  const [importDepth, setImportDepth] = useState<ImportDepth>('Full analysis')
  const [brownfieldSourceMode, setBrownfieldSourceMode] = useState<BrownfieldSourceMode>('Repository')
  const [uploadedFiles, setUploadedFiles] = useState<File[]>([])
  const [dragActive, setDragActive] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const fileInputRef = useRef<HTMLInputElement | null>(null)

  const validName = projectName.trim().length >= 3
  const validDescription = description.trim().length >= 10
  const hasGreenfieldModule = includeAuth || includeAuditLog || includeNotifications

  const filteredRepos = useMemo(() => {
    const normalizedSearch = repoSearch.trim().toLowerCase()
    return brownfieldRepos
      .filter((repo) => repo.provider === gitProvider)
      .filter((repo) => {
        if (repo.provider === 'GitHub') return githubConnected
        if (repo.provider === 'GitLab') return gitlabConnected
        return true
      })
      .filter((repo) => {
        if (normalizedSearch.length === 0) {
          return true
        }
        return (
          repo.name.toLowerCase().includes(normalizedSearch) ||
          repo.fullName.toLowerCase().includes(normalizedSearch)
        )
      })
  }, [gitProvider, githubConnected, gitlabConnected, repoSearch])

  const selectedRepo = useMemo(
    () => brownfieldRepos.find((repo) => repo.id === selectedRepoId) ?? null,
    [selectedRepoId],
  )

  const brownfieldConfigValid = useMemo(() => {
    if (brownfieldSourceMode === 'Upload') {
      return uploadedFiles.length > 0
    }
    return Boolean(
      selectedRepo &&
        selectedBranch &&
        (gitProvider !== 'GitHub' || githubConnected) &&
        (gitProvider !== 'GitLab' || gitlabConnected),
    )
  }, [
    brownfieldSourceMode,
    selectedBranch,
    selectedRepo,
    gitProvider,
    githubConnected,
    gitlabConnected,
    uploadedFiles.length,
  ])

  const stepValid = useMemo(() => {
    if (step === 0) return validName && validDescription
    if (step === 1) {
      if (projectType === 'Greenfield') return hasGreenfieldModule
      return brownfieldConfigValid
    }
    return true
  }, [brownfieldConfigValid, hasGreenfieldModule, projectType, step, validDescription, validName])

  const nextStep = (): void => {
    if (!stepValid) {
      pushToast('Complete required fields before continuing.', 'warning')
      return
    }
    setStep((prev) => Math.min(prev + 1, stepLabels.length - 1))
  }

  const previousStep = (): void => {
    setStep((prev) => Math.max(prev - 1, 0))
  }

  const connectGithub = async (): Promise<void> => {
    setGithubConnecting(true)
    try {
      await new Promise((resolve) => setTimeout(resolve, 700))
      setGithubConnected(true)
      setGithubAccount('specgen-bot')
      pushToast('GitHub connected via OAuth.', 'success')
    } catch (err: any) {
      setGithubConnected(false)
      setGithubAccount('')
      pushToast(`Failed to connect GitHub: ${err?.message ?? 'Unknown error'}`, 'error')
      console.error('connectGithub error', err)
    } finally {
      setGithubConnecting(false)
    }
  }

  const disconnectGithub = (): void => {
    setGithubConnected(false)
    setGithubAccount('')
    if (selectedRepo?.provider === 'GitHub') {
      setSelectedRepoId('')
      setSelectedBranch('')
    }
    pushToast('GitHub connection removed.', 'info')
  }

  const connectGitlab = async (): Promise<void> => {
    setGitlabConnecting(true)
    try {
      await new Promise((resolve) => setTimeout(resolve, 700))
      setGitlabConnected(true)
      setGitlabAccount('specgen-gitlab-bot')
      pushToast('GitLab connected via OAuth.', 'success')
    } catch (err: any) {
      setGitlabConnected(false)
      setGitlabAccount('')
      pushToast(`Failed to connect GitLab: ${err?.message ?? 'Unknown error'}`, 'error')
      console.error('connectGitlab error', err)
    } finally {
      setGitlabConnecting(false)
    }
  }

  const disconnectGitlab = (): void => {
    setGitlabConnected(false)
    setGitlabAccount('')
    if (selectedRepo?.provider === 'GitLab') {
      setSelectedRepoId('')
      setSelectedBranch('')
    }
    pushToast('GitLab connection removed.', 'info')
  }

  const addFiles = (files: FileList | File[]): void => {
    const nextFiles = Array.from(files)
    if (nextFiles.length === 0) {
      return
    }

    setUploadedFiles((prev) => {
      const keys = new Set(prev.map((file) => `${file.name}-${file.size}`))
      const merged = [...prev]
      let actualAdded = 0
      for (const file of nextFiles) {
        const key = `${file.name}-${file.size}`
        if (!keys.has(key)) {
          merged.push(file)
          keys.add(key)
          actualAdded += 1
        }
      }
      if (actualAdded > 0) {
        pushToast(`${actualAdded} file(s) added for brownfield import.`, 'success')
      }
      return merged
    })
  }

  const handleFileInputChange = (event: ChangeEvent<HTMLInputElement>): void => {
    if (!event.target.files) {
      return
    }
    addFiles(event.target.files)
    event.target.value = ''
  }

  const handleDrop = (event: DragEvent<HTMLDivElement>): void => {
    event.preventDefault()
    setDragActive(false)
    if (!event.dataTransfer.files) {
      return
    }
    addFiles(event.dataTransfer.files)
  }

  const handleDragOver = (event: DragEvent<HTMLDivElement>): void => {
    event.preventDefault()
    setDragActive(true)
  }

  const handleDragLeave = (): void => {
    setDragActive(false)
  }

  const removeFile = (index: number): void => {
    setUploadedFiles((prev) => prev.filter((_, i) => i !== index))
  }

  const submitProject = async (): Promise<void> => {
    if (!validName || !validDescription || !stepValid) {
      pushToast('Please resolve validation issues before creating the project.', 'warning')
      return
    }

    setSubmitting(true)
    try {
      // replace simulated delay with actual API call when available
      await new Promise((resolve) => setTimeout(resolve, 700))
      if (projectType === 'Greenfield') {
        pushToast('Greenfield project created (wizard flow).', 'success')
      } else {
        pushToast('Brownfield project created from selected source.', 'success')
      }
      navigate('/projects')
    } catch (err: any) {
      console.error('submitProject failed', err)
      pushToast(`Failed to create project: ${err?.message ?? 'Unknown error'}`, 'error')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <section className="rounded-lg border border-border bg-surface p-8 shadow-card">
      <h1 className="text-2xl font-semibold tracking-tight text-fg">Create Project</h1>
      <p className="mt-2 text-sm text-fg/75">Multi-step wizard for creating a new project.</p>

      <div className="mt-6 grid gap-2 sm:grid-cols-3">
        {stepLabels.map((label, index) => {
          const isActive = index === step
          const isCompleted = index < step
          return (
            <div
              key={label}
              className={[
                'rounded-md border px-3 py-2 text-sm',
                isActive ? 'border-primary bg-primary/10 text-fg' : 'border-border bg-secondary/35 text-fg/70',
                isCompleted ? 'border-success/50 bg-success/10 text-fg' : '',
              ].join(' ')}
            >
              {index + 1}. {label}
            </div>
          )
        })}
      </div>

      <div className="mt-6 rounded-md border border-border bg-secondary/25 p-5">
        {step === 0 ? (
          <div className="space-y-4">
            <Input
              label="Project Name"
              placeholder="Resident Intake Platform"
              value={projectName}
              onChange={(event) => setProjectName(event.target.value)}
              state={projectName.length === 0 || validName ? 'default' : 'error'}
              helperText={projectName.length > 0 && !validName ? 'Use at least 3 characters.' : undefined}
            />
            <Input
              label="Description"
              placeholder="Brief summary of project goals and scope"
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              state={description.length === 0 || validDescription ? 'default' : 'error'}
              helperText={description.length > 0 && !validDescription ? 'Use at least 10 characters.' : undefined}
            />
          </div>
        ) : null}

        {step === 1 ? (
          <div className="space-y-4">
            <Select
              label="Project Type"
              value={projectType}
              onChange={(event) => setProjectType(event.target.value as ProjectType)}
              options={[
                { value: 'Greenfield', label: 'Greenfield (new project)' },
                { value: 'Brownfield', label: 'Brownfield (existing codebase)' },
              ]}
            />

            {projectType === 'Greenfield' ? (
              <div className="space-y-4 rounded-md border border-border/70 bg-surface p-4">
                <Select
                  label="Starter Template"
                  value={template}
                  onChange={(event) => setTemplate(event.target.value as GreenfieldTemplate)}
                  options={[
                    { value: 'Starter SaaS', label: 'Starter SaaS' },
                    { value: 'Internal Ops', label: 'Internal Ops' },
                    { value: 'Public Portal', label: 'Public Portal' },
                  ]}
                />
                <Select
                  label="Database"
                  value={database}
                  onChange={(event) => setDatabase(event.target.value as GreenfieldDatabase)}
                  options={[
                    { value: 'PostgreSQL', label: 'PostgreSQL' },
                    { value: 'MySQL', label: 'MySQL' },
                    { value: 'SQLite', label: 'SQLite' },
                  ]}
                />
                <Select
                  label="Target Stack"
                  value={targetStack}
                  onChange={(event) => setTargetStack(event.target.value)}
                  options={[
                    { value: 'React + FastAPI', label: 'React + FastAPI' },
                    { value: 'Next.js + Node.js', label: 'Next.js + Node.js' },
                    { value: 'Vue + Laravel', label: 'Vue + Laravel' },
                  ]}
                />

                <div className="space-y-2">
                  <p className="text-sm font-medium text-fg">Starter modules</p>
                  <div className="flex flex-col gap-2">
                    <Checkbox label="Authentication" checked={includeAuth} onChange={(event) => setIncludeAuth(event.currentTarget.checked)} />
                    <Checkbox label="Audit Log" checked={includeAuditLog} onChange={(event) => setIncludeAuditLog(event.currentTarget.checked)} />
                    <Checkbox label="Notifications" checked={includeNotifications} onChange={(event) => setIncludeNotifications(event.currentTarget.checked)} />
                  </div>
                  {!hasGreenfieldModule ? <p className="text-xs text-danger">Select at least one starter module.</p> : null}
                </div>
              </div>
            ) : (
              <div className="space-y-4 rounded-md border border-border/70 bg-surface p-4">
                <Select
                  label="Brownfield Source"
                  value={brownfieldSourceMode}
                  onChange={(event) => setBrownfieldSourceMode(event.target.value as BrownfieldSourceMode)}
                  options={[
                    { value: 'Repository', label: 'Repository Picker' },
                    { value: 'Upload', label: 'File Upload (Drag and Drop)' },
                  ]}
                />

                {brownfieldSourceMode === 'Repository' ? (
                  <>
                    {/* Git Provider Select and repository search moved above OAuth panels */}
                    {gitProvider === 'GitHub' ? (
                      <div className="rounded-md border border-border bg-secondary/30 p-3">
                        <p className="text-sm font-medium text-fg">GitHub OAuth</p>
                        <p className="mt-1 text-xs text-fg/70">
                          Connect GitHub to load repositories for brownfield import.
                        </p>
                        <div className="mt-3 flex items-center gap-2">
                          {!githubConnected ? (
                            <Button
                              type="button"
                              variant="secondary"
                              onClick={() => void connectGithub()}
                              disabled={githubConnecting}
                            >
                              {githubConnecting ? 'Connecting...' : 'Connect GitHub'}
                            </Button>
                          ) : (
                            <>
                              <span className="rounded-md bg-success/15 px-2 py-1 text-xs text-success">
                                Connected as {githubAccount}
                              </span>
                              <Button type="button" variant="ghost" onClick={disconnectGithub}>
                                Disconnect
                              </Button>
                            </>
                          )}
                        </div>
                      </div>
                    ) : null}

                    {gitProvider === 'GitLab' ? (
                      <div className="rounded-md border border-border bg-secondary/30 p-3">
                        <p className="text-sm font-medium text-fg">GitLab OAuth</p>
                        <p className="mt-1 text-xs text-fg/70">
                          Connect GitLab to load repositories for brownfield import.
                        </p>
                        <div className="mt-3 flex items-center gap-2">
                          {!gitlabConnected ? (
                            <Button
                              type="button"
                              variant="secondary"
                              onClick={() => void connectGitlab()}
                              disabled={gitlabConnecting}
                            >
                              {gitlabConnecting ? 'Connecting...' : 'Connect GitLab'}
                            </Button>
                          ) : (
                            <>
                              <span className="rounded-md bg-success/15 px-2 py-1 text-xs text-success">
                                Connected as {gitlabAccount}
                              </span>
                              <Button type="button" variant="ghost" onClick={disconnectGitlab}>
                                Disconnect
                              </Button>
                            </>
                          )}
                        </div>
                      </div>
                    ) : null}

                    <div className="grid gap-3 md:grid-cols-2">
                      <Select
                        label="Git Provider"
                        value={gitProvider}
                        onChange={(event) => {
                          const nextProvider = event.target.value as GitProvider
                          setGitProvider(nextProvider)
                          setSelectedRepoId('')
                          setSelectedBranch('')
                        }}
                        options={[
                          { value: 'GitHub', label: 'GitHub' },
                          { value: 'GitLab', label: 'GitLab' },
                        ]}
                      />
                      <Input
                        label="Search Repositories"
                        placeholder="Find repo by name"
                        value={repoSearch}
                        onChange={(event) => setRepoSearch(event.target.value)}
                        disabled={
                          (gitProvider === 'GitHub' && !githubConnected) ||
                          (gitProvider === 'GitLab' && !gitlabConnected)
                        }
                      />
                    </div>

                    <div className="space-y-2">
                      <p className="text-sm font-medium text-fg">Repository Picker</p>
                      {filteredRepos.length === 0 ? (
                        <p className="rounded-md border border-border bg-secondary/35 px-3 py-2 text-xs text-fg/70">
                          No repositories found for current filter.
                        </p>
                      ) : (
                        <div className="grid gap-2">
                          {filteredRepos.map((repo) => {
                            const isSelected = repo.id === selectedRepoId
                            return (
                              <button
                                key={repo.id}
                                type="button"
                                disabled={
                                  (gitProvider === 'GitHub' && !githubConnected) ||
                                  (gitProvider === 'GitLab' && !gitlabConnected)
                                }
                                className={[
                                  'rounded-md border px-3 py-2 text-left text-sm transition',
                                  isSelected
                                    ? 'border-primary bg-primary/10'
                                    : 'border-border bg-secondary/20 hover:bg-secondary/40',
                                ].join(' ')}
                                onClick={() => {
                                  setSelectedRepoId(repo.id)
                                  setSelectedBranch(repo.defaultBranch)
                                }}
                              >
                                <p className="font-medium text-fg">{repo.fullName}</p>
                                <p className="text-xs text-fg/70">
                                  Default branch: {repo.defaultBranch} · Last commit:{' '}
                                  {new Date(repo.lastCommitAt).toLocaleDateString()}
                                </p>
                              </button>
                            )
                          })}
                        </div>
                      )}
                    </div>

                    <div className="grid gap-3 md:grid-cols-2">
                      <Select
                        label="Branch"
                        value={selectedBranch}
                        onChange={(event) => setSelectedBranch(event.target.value)}
                        options={
                          selectedRepo
                            ? selectedRepo.branches.map((branch) => ({ value: branch, label: branch }))
                            : [{ value: '', label: 'Select a repository first' }]
                        }
                        disabled={!selectedRepo}
                      />
                      <Select
                        label="Import Depth"
                        value={importDepth}
                        onChange={(event) => setImportDepth(event.target.value as ImportDepth)}
                        options={[
                          { value: 'Full analysis', label: 'Full analysis' },
                          { value: 'Shallow scan', label: 'Shallow scan' },
                        ]}
                      />
                    </div>

                    {selectedRepo ? (
                      <p className="text-xs text-fg/70">Selected URL: {selectedRepo.url}</p>
                    ) : (
                      <p className="text-xs text-danger">Pick a repository to continue.</p>
                    )}
                  </>
                ) : (
                  <div className="space-y-3">
                    <div
                      className={[
                        'rounded-md border-2 border-dashed p-6 text-center transition',
                        dragActive ? 'border-primary bg-primary/10' : 'border-border bg-secondary/25',
                      ].join(' ')}
                      onDrop={handleDrop}
                      onDragOver={handleDragOver}
                      onDragLeave={handleDragLeave}
                    >
                      <p className="text-sm font-medium text-fg">Drag and drop files here</p>
                      <p className="mt-1 text-xs text-fg/70">
                        Supports docs, exports, and archives for brownfield analysis.
                      </p>
                      <div className="mt-3">
                        <Button type="button" variant="secondary" onClick={() => fileInputRef.current?.click()}>
                          Browse Files
                        </Button>
                        <input
                          ref={fileInputRef}
                          type="file"
                          className="hidden"
                          multiple
                          onChange={handleFileInputChange}
                        />
                      </div>
                    </div>

                    {uploadedFiles.length === 0 ? (
                      <p className="text-xs text-danger">Upload at least one file to continue.</p>
                    ) : (
                      <div className="space-y-2 rounded-md border border-border bg-secondary/20 p-3">
                        <p className="text-xs font-semibold uppercase tracking-widest text-fg/60">
                          Uploaded Files ({uploadedFiles.length})
                        </p>
                        {uploadedFiles.map((file, index) => (
                          <div
                            key={`${file.name}-${file.size}-${index}`}
                            className="flex items-center justify-between gap-3 text-sm"
                          >
                            <span className="truncate text-fg/85">{file.name}</span>
                            <Button type="button" variant="ghost" size="sm" onClick={() => removeFile(index)}>
                              Remove
                            </Button>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
        ) : null}

        {step === 2 ? (
          <div className="space-y-3 text-sm text-fg/80">
            <p>
              <span className="font-semibold text-fg">Name:</span> {projectName}
            </p>
            <p>
              <span className="font-semibold text-fg">Description:</span> {description}
            </p>
            <p>
              <span className="font-semibold text-fg">Type:</span> {projectType}
            </p>

            {projectType === 'Greenfield' ? (
              <>
                <p>
                  <span className="font-semibold text-fg">Template:</span> {template}
                </p>
                <p>
                  <span className="font-semibold text-fg">Database:</span> {database}
                </p>
                <p>
                  <span className="font-semibold text-fg">Stack:</span> {targetStack}
                </p>
                <p>
                  <span className="font-semibold text-fg">Modules:</span>{' '}
                  {[includeAuth && 'Auth', includeAuditLog && 'Audit Log', includeNotifications && 'Notifications']
                    .filter(Boolean)
                    .join(', ')}
                </p>
              </>
            ) : (
              <>
                <p>
                  <span className="font-semibold text-fg">Git Provider:</span> {gitProvider}
                </p>
                {gitProvider === 'GitHub' ? (
                  <p>
                    <span className="font-semibold text-fg">GitHub OAuth:</span>{' '}
                    {githubConnected ? `Connected (${githubAccount})` : 'Not connected'}
                  </p>
                ) : null}
                {gitProvider === 'GitLab' ? (
                  <p>
                    <span className="font-semibold text-fg">GitLab OAuth:</span>{' '}
                    {gitlabConnected ? `Connected (${gitlabAccount})` : 'Not connected'}
                  </p>
                ) : null}
                <p>
                  <span className="font-semibold text-fg">Source Mode:</span> {brownfieldSourceMode}
                </p>
                {brownfieldSourceMode === 'Repository' ? (
                  <>
                    <p>
                      <span className="font-semibold text-fg">Repository:</span>{' '}
                      {selectedRepo?.fullName ?? 'Not selected'}
                    </p>
                    <p>
                      <span className="font-semibold text-fg">Branch:</span> {selectedBranch || 'Not selected'}
                    </p>
                    <p>
                      <span className="font-semibold text-fg">Import Depth:</span> {importDepth}
                    </p>
                  </>
                ) : (
                  <p>
                    <span className="font-semibold text-fg">Uploaded Files:</span>{' '}
                    {uploadedFiles.length === 0
                      ? 'None'
                      : uploadedFiles.map((file) => file.name).join(', ')}
                  </p>
                )}
              </>
            )}
          </div>
        ) : null}
      </div>

      <div className="mt-6 flex items-center justify-between">
        <Button variant="ghost" onClick={previousStep} disabled={step === 0 || submitting}>
          Back
        </Button>

        {step < stepLabels.length - 1 ? (
          <Button onClick={nextStep} disabled={!stepValid || submitting}>
            Next
          </Button>
        ) : (
          <Button onClick={() => void submitProject()} disabled={submitting}>
            {submitting ? 'Creating...' : 'Create Project'}
          </Button>
        )}
      </div>
    </section>
  )
}
