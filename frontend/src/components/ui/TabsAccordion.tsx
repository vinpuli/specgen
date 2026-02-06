import { useState, type ReactNode } from 'react'

type TabItem = {
  id: string
  label: string
  content: ReactNode
}

type TabsProps = {
  items: TabItem[]
  defaultTabId?: string
}

export function Tabs({ items, defaultTabId }: TabsProps) {
  const [active, setActive] = useState(defaultTabId ?? items[0]?.id ?? '')
  const current = items.find((item) => item.id === active) ?? items[0]

  return (
    <div className="rounded-lg border border-border bg-surface">
      <div className="flex border-b border-border p-1">
        {items.map((item) => (
          <button
            key={item.id}
            type="button"
            onClick={() => setActive(item.id)}
            className={[
              'rounded-md px-3 py-2 text-sm font-medium',
              item.id === current?.id ? 'bg-primary text-primary-foreground' : 'text-fg/70 hover:bg-secondary',
            ].join(' ')}
          >
            {item.label}
          </button>
        ))}
      </div>
      <div className="p-4 text-sm text-fg/80">{current?.content}</div>
    </div>
  )
}

type AccordionItem = {
  id: string
  title: string
  content: ReactNode
}

type AccordionProps = {
  items: AccordionItem[]
}

export function Accordion({ items }: AccordionProps) {
  const [openId, setOpenId] = useState<string | null>(items[0]?.id ?? null)

  return (
    <div className="rounded-lg border border-border bg-surface">
      {items.map((item, index) => {
        const isOpen = openId === item.id
        return (
          <section key={item.id} className={index > 0 ? 'border-t border-border' : ''}>
            <button
              type="button"
              className="flex w-full items-center justify-between px-4 py-3 text-left text-sm font-medium text-fg"
              onClick={() => setOpenId(isOpen ? null : item.id)}
              aria-expanded={isOpen}
            >
              <span>{item.title}</span>
              <span>{isOpen ? '-' : '+'}</span>
            </button>
            {isOpen ? <div className="px-4 pb-4 text-sm text-fg/75">{item.content}</div> : null}
          </section>
        )
      })}
    </div>
  )
}
