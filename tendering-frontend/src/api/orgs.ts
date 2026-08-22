import axios from 'axios';
import type { OrgMember, PendingInvitation, InvitationPreview, Organisation, OrgRole } from '../types';

const api = axios.create({ baseURL: import.meta.env.VITE_API_URL ?? 'http://localhost:8000' });

api.interceptors.request.use((config) => {
  const stored = localStorage.getItem('sb-session');
  if (stored) {
    try {
      const { access_token } = JSON.parse(stored);
      config.headers.Authorization = `Bearer ${access_token}`;
    } catch { /* no valid session */ }
  }
  return config;
});

// ─── Org members ──────────────────────────────────────────────────────────────

export async function getOrgMembers(orgId: string): Promise<OrgMember[]> {
  const { data } = await api.get(`/orgs/${orgId}/members`);
  return data.members ?? data;
}

export async function inviteMember(orgId: string, email: string, role: OrgRole, name?: string) {
  const { data } = await api.post(`/orgs/${orgId}/invite`, { email, role, name });
  return data as { invite_link: string; invite_token: string; email: string; role: string; email_sent: boolean };
}

export async function removeMember(orgId: string, userId: string): Promise<void> {
  await api.delete(`/orgs/${orgId}/members/${userId}`);
}

export async function changeMemberRole(orgId: string, userId: string, role: OrgRole): Promise<void> {
  await api.patch(`/orgs/${orgId}/members/${userId}`, { role });
}

export async function leaveOrg(orgId: string): Promise<void> {
  await api.delete(`/orgs/${orgId}/members/me`);
}

// ─── Invitations ──────────────────────────────────────────────────────────────

export async function getPendingInvitations(orgId: string): Promise<PendingInvitation[]> {
  const { data } = await api.get(`/orgs/${orgId}/invitations`);
  return data.invitations ?? data;
}

export async function cancelInvitation(orgId: string, token: string): Promise<void> {
  await api.delete(`/orgs/${orgId}/invitations/${token}`);
}

export async function resendInvitation(orgId: string, token: string) {
  const { data } = await api.post(`/orgs/${orgId}/invitations/${token}/resend`);
  return data as { email_sent: boolean; invite_link: string };
}

// ─── Public invite accept ─────────────────────────────────────────────────────

export async function getInvitation(token: string): Promise<InvitationPreview> {
  const { data } = await api.get(`/invitations/${token}`);
  return data;
}

export async function acceptInvitation(token: string) {
  const { data } = await api.post(`/invitations/${token}/accept`);
  return data as { org_id: string; org_name: string; role: string };
}

// ─── Platform admin ───────────────────────────────────────────────────────────

export async function getAllOrgs(): Promise<Organisation[]> {
  const { data } = await api.get('/platform/orgs');
  return data.orgs ?? data;
}

export async function createOrg(name: string, plan: string, adminEmail: string, adminName?: string) {
  const { data } = await api.post('/platform/orgs', { name, plan, admin_email: adminEmail, admin_name: adminName });
  return data as Organisation & { invite_link?: string };
}

export async function updateOrg(orgId: string, patch: { plan?: string; status?: string; name?: string }) {
  const { data } = await api.patch(`/platform/orgs/${orgId}`, patch);
  return data as Organisation;
}

export async function deleteOrg(orgId: string): Promise<void> {
  await api.delete(`/platform/orgs/${orgId}`);
}
