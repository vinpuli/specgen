import { useMemo, useState, type FormEvent } from 'react'
import { Button, Input, Select, useToast } from '../components/ui'
import { useWorkspaceStore, type MemberRole } from '../store/workspaceStore'

const roleOptions = [
  { value: 'Owner', label: 'Owner' },
  { value: 'Admin', label: 'Admin' },
  { value: 'Editor', label: 'Editor' },
  { value: 'Viewer', label: 'Viewer' },
]

export function WorkspaceMembersPage() {
  const { pushToast } = useToast()
  const activeWorkspaceId = useWorkspaceStore((state) => state.activeWorkspaceId)
  const workspaces = useWorkspaceStore((state) => state.workspaces)
  const members = useWorkspaceStore((state) => state.members)
  const invites = useWorkspaceStore((state) => state.invites)
  const updateMemberRole = useWorkspaceStore((state) => state.updateMemberRole)
  const removeMember = useWorkspaceStore((state) => state.removeMember)
  const inviteMember = useWorkspaceStore((state) => state.inviteMember)
  const revokeInvite = useWorkspaceStore((state) => state.revokeInvite)
  const resendInvite = useWorkspaceStore((state) => state.resendInvite)

  const [inviteEmail, setInviteEmail] = useState('')
  const [inviteRole, setInviteRole] = useState<MemberRole>('Viewer')

  const activeWorkspace = useMemo(
    () => workspaces.find((workspace) => workspace.id === activeWorkspaceId) ?? null,
    [activeWorkspaceId, workspaces],
  )
  const workspaceMembers = useMemo(
    () => members.filter((member) => member.workspaceId === activeWorkspaceId),
    [activeWorkspaceId, members],
  )
  const workspaceInvites = useMemo(
    () => invites.filter((invite) => invite.workspaceId === activeWorkspaceId),
    [activeWorkspaceId, invites],
  )

  if (!activeWorkspace) {
    return <section className="rounded-lg border border-border bg-surface p-8 shadow-card">No active workspace found.</section>
  }

  const validEmail = /\S+@\S+\.\S+/.test(inviteEmail)

  const handleInvite = (event: FormEvent<HTMLFormElement>): void => {
    event.preventDefault()
    if (!validEmail) {
      pushToast('Enter a valid email address for invitation.', 'warning')
      return
    }

    inviteMember(activeWorkspace.id, inviteEmail.trim(), inviteRole)
    pushToast(`Invitation sent to ${inviteEmail.trim()}.`, 'success')
    setInviteEmail('')
    setInviteRole('Viewer')
  }

  return (
    <section className="space-y-6">
      <div className="rounded-lg border border-border bg-surface p-8 shadow-card">
        <h1 className="text-2xl font-semibold tracking-tight text-fg">Workspace Members</h1>
        <p className="mt-2 text-sm text-fg/75">Manage member roles and invitations for {activeWorkspace.name}.</p>

        <form className="mt-5 grid gap-3 rounded-md border border-border bg-secondary/35 p-4 md:grid-cols-[1fr_180px_auto]" onSubmit={handleInvite}>
          <Input
            label="Invite by email"
            placeholder="member@company.com"
            value={inviteEmail}
            onChange={(event) => setInviteEmail(event.target.value)}
            state={inviteEmail.length === 0 || validEmail ? 'default' : 'error'}
            helperText={inviteEmail.length > 0 && !validEmail ? 'Use a valid email address.' : undefined}
          />
          <Select
            label="Role"
            value={inviteRole}
            onChange={(event) => setInviteRole(event.target.value as MemberRole)}
            options={roleOptions}
          />
          <div className="self-end">
            <Button type="submit" disabled={!validEmail}>
              Send Invite
            </Button>
          </div>
        </form>
      </div>

      <div className="rounded-lg border border-border bg-surface p-6 shadow-card">
        <h2 className="text-lg font-semibold text-fg">Members</h2>
        <div className="mt-4 overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead className="text-left text-xs uppercase tracking-widest text-fg/60">
              <tr>
                <th className="pb-2">Name</th>
                <th className="pb-2">Email</th>
                <th className="pb-2">Role</th>
                <th className="pb-2">Status</th>
                <th className="pb-2">Actions</th>
              </tr>
            </thead>
            <tbody className="text-fg/85">
              {workspaceMembers.map((member) => (
                <tr key={member.id} className="border-t border-border">
                  <td className="py-3">{member.name}</td>
                  <td className="py-3">{member.email}</td>
                  <td className="py-3">
                    <select
                      className="h-9 rounded-md border border-border bg-surface px-2"
                      value={member.role}
                      onChange={(event) => {
                        updateMemberRole(member.id, event.target.value as MemberRole)
                        pushToast(`Role updated for ${member.email}.`, 'info')
                      }}
                    >
                      {roleOptions.map((option) => (
                        <option key={option.value} value={option.value}>
                          {option.label}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td className="py-3">{member.status}</td>
                  <td className="py-3">
                    <Button
                      variant="ghost"
                      onClick={() => {
                        removeMember(member.id)
                        pushToast(`Removed ${member.email} from workspace.`, 'warning')
                      }}
                    >
                      Remove
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="rounded-lg border border-border bg-surface p-6 shadow-card">
        <h2 className="text-lg font-semibold text-fg">Pending Invitations</h2>
        <div className="mt-4 space-y-3">
          {workspaceInvites.length === 0 ? (
            <p className="text-sm text-fg/70">No pending invitations.</p>
          ) : (
            workspaceInvites.map((invite) => (
              <div
                key={invite.id}
                className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-border bg-secondary/35 px-4 py-3"
              >
                <div>
                  <p className="text-sm font-medium text-fg">{invite.email}</p>
                  <p className="text-xs text-fg/65">
                    {invite.role} · {invite.status} · Invited {new Date(invite.invitedAt).toLocaleString()}
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <Button
                    variant="secondary"
                    onClick={() => {
                      resendInvite(invite.id)
                      pushToast(`Invitation resent to ${invite.email}.`, 'info')
                    }}
                  >
                    Resend
                  </Button>
                  <Button
                    variant="ghost"
                    onClick={() => {
                      revokeInvite(invite.id)
                      pushToast(`Invitation revoked for ${invite.email}.`, 'warning')
                    }}
                  >
                    Revoke
                  </Button>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </section>
  )
}
