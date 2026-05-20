import ReactDOM from 'react-dom/client'
import { AppProviders } from '@/app/providers/AppProviders'
import { createAppQueryClient } from '@/app/initialization/query-client'
import { createAppRouter } from '@/app/router'
import '@/index.css'

let router!: ReturnType<typeof createAppRouter>
const queryClient = createAppQueryClient(() => router)
router = createAppRouter(queryClient)

const rootElement = document.getElementById('root')!
if (!rootElement.innerHTML) {
  const root = ReactDOM.createRoot(rootElement)
  root.render(<AppProviders queryClient={queryClient} router={router} />)
}
