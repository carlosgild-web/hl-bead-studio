import { ChatPanel } from './ChatPanel'
import { OutputTabs } from './OutputTabs'
import { ParameterPanel } from './ParameterPanel'
import { ViewerPanel } from './ViewerPanel'

/** Chat (left), parameter panel (center), 3D viewer (right); drawing and renders below. */
export function StudioPage() {
  return (
    <div className="grid gap-4 lg:h-[calc(100svh-7rem)] lg:grid-cols-[minmax(20rem,26rem)_1fr]">
      <ChatPanel />
      <div className="min-h-0 space-y-4 lg:overflow-y-auto lg:pr-1">
        <div className="grid gap-4 rounded-lg border bg-card p-4 xl:grid-cols-2">
          <ParameterPanel />
          <ViewerPanel />
        </div>
        <div className="rounded-lg border bg-card p-4">
          <OutputTabs />
        </div>
      </div>
    </div>
  )
}
