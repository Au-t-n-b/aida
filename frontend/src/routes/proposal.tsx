// @ts-nocheck
import ProposalScreen from '@/components/screens/proposal';
import { ProposalDataProvider } from '@/hooks/useProposalData';

/** 交付预案 · 主内容（壳层见 WorkspaceShell） */
export default function ProposalPage() {
  return (
    <ProposalDataProvider>
      <ProposalScreen />
    </ProposalDataProvider>
  );
}
