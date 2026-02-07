import { create } from 'zustand'

export type WorkspacePlan = 'Starter' | 'Pro' | 'Enterprise'
export type MemberRole = 'Owner' | 'Admin' | 'Editor' | 'Viewer'

export type Workspace = {
  id: string
  name: string
  slug: string
  description: string
  plan: WorkspacePlan
  membersCount: number
  projectsCount: number
  createdAt: string
}

export type WorkspaceMember = {
  id: string
  workspaceId: string
  name: string
  email: string
  role: MemberRole
  status: 'Active' | 'Pending'
}

export type WorkspaceInvite = {
  id: string
  workspaceId: string
  email: string
  role: MemberRole
  invitedAt: string
  status: 'Pending' | 'Accepted' | 'Expired'
}

type WorkspaceState = {
  activeWorkspaceId: string
  workspaces: Workspace[]
  members: WorkspaceMember[]
  invites: WorkspaceInvite[]
  setActiveWorkspace: (workspaceId: string) => void
  createWorkspace: (input: {
    name: string
    slug: string
    description: string
    plan: WorkspacePlan
  }) => Workspace
  updateWorkspace: (workspaceId: string, patch: Partial<Omit<Workspace, 'id' | 'createdAt'>>) => void
  updateMemberRole: (memberId: string, role: MemberRole) => void
  removeMember: (memberId: string) => void
  inviteMember: (workspaceId: string, email: string, role: MemberRole) => WorkspaceInvite
  revokeInvite: (inviteId: string) => void
  resendInvite: (inviteId: string) => void
}

const initialWorkspaces: Workspace[] = [
  {
    id: 'ws-default',
    name: 'Default Workspace',
    slug: 'default-workspace',
    description: 'Primary workspace for product and engineering decisions.',
    plan: 'Pro',
    membersCount: 8,
    projectsCount: 12,
    createdAt: '2026-01-10',
  },
  {
    id: 'ws-clinical',
    name: 'Clinical Team',
    slug: 'clinical-team',
    description: 'Clinical workflows, forms, and care automation.',
    plan: 'Enterprise',
    membersCount: 14,
    projectsCount: 5,
    createdAt: '2026-01-28',
  },
]

const initialMembers: WorkspaceMember[] = [
  {
    id: 'm-1',
    workspaceId: 'ws-default',
    name: 'SpecGen Owner',
    email: 'owner@specgen.dev',
    role: 'Owner',
    status: 'Active',
  },
  {
    id: 'm-2',
    workspaceId: 'ws-default',
    name: 'Priya Patel',
    email: 'priya@specgen.dev',
    role: 'Admin',
    status: 'Active',
  },
  {
    id: 'm-3',
    workspaceId: 'ws-default',
    name: 'Luca Kim',
    email: 'luca@specgen.dev',
    role: 'Editor',
    status: 'Active',
  },
]

const initialInvites: WorkspaceInvite[] = [
  {
    id: 'inv-1',
    workspaceId: 'ws-default',
    email: 'new.member@specgen.dev',
    role: 'Viewer',
    invitedAt: '2026-02-03T09:30:00.000Z',
    status: 'Pending',
  },
]

export const useWorkspaceStore = create<WorkspaceState>((set) => ({
  activeWorkspaceId: initialWorkspaces[0].id,
  workspaces: initialWorkspaces,
  members: initialMembers,
  invites: initialInvites,
  setActiveWorkspace: (workspaceId) => set({ activeWorkspaceId: workspaceId }),
  createWorkspace: (input) => {
    const newWorkspace: Workspace = {
      id: `ws-${Date.now()}`,
      name: input.name.trim(),
      slug: input.slug.trim(),
      description: input.description.trim(),
      plan: input.plan,
      membersCount: 1,
      projectsCount: 0,
      createdAt: new Date().toISOString().slice(0, 10),
    }
    set((state) => ({
      activeWorkspaceId: newWorkspace.id,
      workspaces: [newWorkspace, ...state.workspaces],
      members: [
        ...state.members,
        {
          id: `m-${Date.now()}`,
          workspaceId: newWorkspace.id,
          name: 'Workspace Owner',
          email: 'owner@specgen.dev',
          role: 'Owner',
          status: 'Active',
        },
      ],
    }))
    return newWorkspace
  },
  updateWorkspace: (workspaceId, patch) =>
    set((state) => ({
      workspaces: state.workspaces.map((workspace) =>
        workspace.id === workspaceId ? { ...workspace, ...patch } : workspace,
      ),
    })),
  updateMemberRole: (memberId, role) =>
    set((state) => ({
      members: state.members.map((member) => (member.id === memberId ? { ...member, role } : member)),
    })),
  removeMember: (memberId) =>
    set((state) => ({
      members: state.members.filter((member) => member.id !== memberId),
    })),
  inviteMember: (workspaceId, email, role) => {
    const invite: WorkspaceInvite = {
      id: `inv-${Date.now()}`,
      workspaceId,
      email: email.trim().toLowerCase(),
      role,
      invitedAt: new Date().toISOString(),
      status: 'Pending',
    }
    set((state) => ({
      invites: [invite, ...state.invites],
    }))
    return invite
  },
  revokeInvite: (inviteId) =>
    set((state) => ({
      invites: state.invites.filter((invite) => invite.id !== inviteId),
    })),
  resendInvite: (inviteId) =>
    set((state) => ({
      invites: state.invites.map((invite) =>
        invite.id === inviteId
          ? { ...invite, invitedAt: new Date().toISOString(), status: 'Pending' }
          : invite,
      ),
    })),
}))
