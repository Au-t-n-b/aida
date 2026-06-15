import { Navigate, useSearchParams } from 'react-router-dom';

/** /twin 及 ?view= 旧链接兼容重定向 */
export default function TwinRedirectPage() {
  const [params] = useSearchParams();
  const view = params.get('view');
  if (view === 'physical') return <Navigate to="/twin/physical" replace />;
  if (view === 'digital') return <Navigate to="/twin/digital" replace />;
  return <Navigate to="/twin/survey" replace />;
}
