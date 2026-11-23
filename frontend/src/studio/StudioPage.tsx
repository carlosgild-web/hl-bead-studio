import { ChatPanel } from './ChatPanel'
import { dimProps, useFocus } from './context'
import { OutputTabs } from './OutputTabs'
import { ParameterPanel } from './ParameterPanel'
import { ViewerPanel } from './ViewerPanel'

/** Chat (left), parameter panel (center), 3D viewer (right); drawing and renders below. */
export function StudioPage() {
  // While a decision waits in the chat, the rest of the studio is dimmed (focus mode).
  const focus = useFocus()
  return (
    <div className="grid gap-4 lg:h-full lg:min-h-[32rem] lg:grid-cols-[minmax(20rem,26rem)_minmax(0,1fr)]">
      <ChatPanel />
      <div {...dimProps(focus !== null, 'min-h-0 space-y-4 lg:overflow-y-auto lg:pr-1')}>
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
