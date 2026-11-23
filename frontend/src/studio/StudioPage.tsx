import { ChatPanel } from './ChatPanel'
import { dimProps, useFocus } from './context'
import { OutputTabs } from './OutputTabs'
import { ParameterPanel } from './ParameterPanel'
import { ViewerPanel } from './ViewerPanel'

/** Chat (left), parameter panel (center), 3D viewer (right); drawing and renders below. */
export function StudioPage() {
  // While a decision waits in the chat, the rest of the studio is dimmed (focus mode).
  const focus = useFocus()
  // A card or the Start-over question dims the whole right column; an open workflow step
  // dims everything there but the workflow itself (inside the parameter panel).
  const step = focus?.kind === 'step'
  // The Render step uses the color or finish chosen in the viewer, so it stays usable then.
  const viewerInUse = focus?.kind === 'step' && focus.step === 'render'
  return (
    <div className="grid gap-4 lg:h-full lg:min-h-[32rem] lg:grid-cols-[minmax(20rem,26rem)_minmax(0,1fr)]">
      <ChatPanel />
      <div {...dimProps(focus !== null && !step, 'min-h-0 space-y-4 lg:overflow-y-auto lg:pr-1')}>
        <div className="grid gap-4 rounded-lg border bg-card p-4 xl:grid-cols-2">
          <ParameterPanel />
          <div {...dimProps(step && !viewerInUse)}>
            <ViewerPanel />
          </div>
        </div>
        <div {...dimProps(step, 'rounded-lg border bg-card p-4')}>
          <OutputTabs />
        </div>
      </div>
    </div>
  )
}
