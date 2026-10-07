import { Redirect } from 'expo-router';

import { Loading } from '@/components/ui';
import { useSession } from '@/lib/session';

export default function Index() {
  const { ready, me } = useSession();
  if (!ready) return <Loading dark />;
  return <Redirect href={me ? '/accueil' : '/langue'} />;
}
