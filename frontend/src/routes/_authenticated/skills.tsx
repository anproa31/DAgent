import { useState } from 'react'
import { createFileRoute } from '@tanstack/react-router'
import { IconTrash } from '@tabler/icons-react'
import { toast } from 'sonner'
import {
  useCreateSkill,
  useDeleteSkill,
  useSkills,
  useUpdateSkill,
} from '@/hooks/use-memory'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'

export const Route = createFileRoute('/_authenticated/skills')({
  component: SkillsPage,
})

const EMPTY = { name: '', description: '', template: '', skill_type: 'sql' }

function SkillsPage() {
  const { data: skills = [], isLoading } = useSkills()
  const create = useCreateSkill()
  const update = useUpdateSkill()
  const remove = useDeleteSkill()

  const [form, setForm] = useState(EMPTY)
  const [editing, setEditing] = useState<string | null>(null)

  const reset = () => {
    setForm(EMPTY)
    setEditing(null)
  }

  const save = async () => {
    if (!form.name.trim()) {
      toast.error('Name is required')
      return
    }
    try {
      if (editing) {
        await update.mutateAsync({
          skillId: editing,
          body: { name: form.name, description: form.description, template: form.template },
        })
        toast.success('Skill updated')
      } else {
        await create.mutateAsync(form)
        toast.success('Skill added')
      }
      reset()
    } catch {
      toast.error('Failed to save skill')
    }
  }

  return (
    <div className="container mx-auto max-w-4xl p-6">
      <h1 className="text-2xl font-bold">Skills &amp; Templates</h1>
      <p className="mt-1 text-muted-foreground">
        Add SQL templates, chart recipes, or pipeline patterns your agent can reuse.
      </p>

      <div className="mt-6 space-y-3 rounded-xl border bg-muted/30 p-4">
        <h2 className="font-semibold">{editing ? 'Edit skill' : 'Add new skill'}</h2>
        <div className="space-y-2">
          <Label htmlFor="skill-name">Name</Label>
          <Input
            id="skill-name"
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="skill-desc">Description (used for semantic search)</Label>
          <Input
            id="skill-desc"
            value={form.description}
            onChange={(e) => setForm({ ...form, description: e.target.value })}
          />
        </div>
        <div className="space-y-2">
          <Label>Type</Label>
          <Select
            value={form.skill_type}
            onValueChange={(v) => setForm({ ...form, skill_type: v })}
            disabled={!!editing}
          >
            <SelectTrigger className="w-48">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="sql">SQL template</SelectItem>
              <SelectItem value="chart">Chart recipe</SelectItem>
              <SelectItem value="pipeline">Pipeline pattern</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-2">
          <Label htmlFor="skill-template">Template / code</Label>
          <Textarea
            id="skill-template"
            rows={6}
            className="font-mono text-sm"
            value={form.template}
            onChange={(e) => setForm({ ...form, template: e.target.value })}
          />
        </div>
        <div className="flex gap-2">
          <Button onClick={save} disabled={create.isPending || update.isPending}>
            {editing ? 'Save changes' : 'Add skill'}
          </Button>
          {editing && (
            <Button variant="outline" onClick={reset}>
              Cancel
            </Button>
          )}
        </div>
      </div>

      <h2 className="mt-8 mb-3 text-lg font-semibold">All Skills</h2>
      {isLoading ? (
        <p className="text-muted-foreground">Loading…</p>
      ) : (
        <div className="space-y-3">
          {skills.map((skill) => (
            <div key={skill.skill_id} className="rounded-lg border p-4">
              <div className="flex items-start justify-between gap-2">
                <div className="flex items-center gap-2">
                  <strong>{skill.name}</strong>
                  <Badge variant="outline">{skill.type}</Badge>
                  {skill.is_default && (
                    <span className="text-xs text-muted-foreground">(built-in)</span>
                  )}
                </div>
                <div className="flex gap-1">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => {
                      setEditing(skill.skill_id)
                      setForm({
                        name: skill.name,
                        description: skill.description,
                        template: skill.template,
                        skill_type: skill.type,
                      })
                    }}
                  >
                    Edit
                  </Button>
                  {!skill.is_default && (
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8 text-muted-foreground hover:text-destructive"
                      disabled={remove.isPending}
                      onClick={() => remove.mutate(skill.skill_id)}
                    >
                      <IconTrash className="h-4 w-4" />
                    </Button>
                  )}
                </div>
              </div>
              <p className="mt-2 text-sm text-muted-foreground">{skill.description}</p>
              <pre className="mt-2 overflow-auto rounded bg-muted p-3 text-xs">
                {skill.template}
              </pre>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
