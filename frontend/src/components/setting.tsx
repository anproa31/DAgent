import { useState } from 'react'
import { useSettings } from '@/context/settings-context'
import { useTranslation } from '@/context/locale-context'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Settings as SettingsIcon } from 'lucide-react'

export function Setting() {
  const {
    baseUrl,
    apiKey,
    embeddingBaseUrl,
    embeddingModel,
    setBaseUrl,
    setApiKey,
    setEmbeddingBaseUrl,
    setEmbeddingModel,
    resetSettings,
  } = useSettings()
  const { t } = useTranslation()
  const [open, setOpen] = useState(false)
  const [tempBaseUrl, setTempBaseUrl] = useState(baseUrl)
  const [tempApiKey, setTempApiKey] = useState(apiKey)
  const [tempEmbedUrl, setTempEmbedUrl] = useState(embeddingBaseUrl)
  const [tempEmbedModel, setTempEmbedModel] = useState(embeddingModel)

  const onSave = () => {
    setBaseUrl(tempBaseUrl.trim())
    setApiKey(tempApiKey.trim())
    setEmbeddingBaseUrl(tempEmbedUrl.trim())
    setEmbeddingModel(tempEmbedModel.trim())
    setOpen(false)
  }

  const onReset = () => {
    resetSettings()
    setTempBaseUrl('http://localhost:11434')
    setTempApiKey('')
    setTempEmbedUrl('http://localhost:11434/v1')
    setTempEmbedModel('nomic-embed-text')
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="ghost" size="icon" aria-label={t('settings.aria')} title={t('settings.aria')}>
          <SettingsIcon className="h-5 w-5" />
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{t('settings.title')}</DialogTitle>
        </DialogHeader>
        <div className="space-y-4 py-2">
          <div className="space-y-2">
            <Label htmlFor="base_url">{t('settings.baseUrl')}</Label>
            <Input
              id="base_url"
              placeholder="https://example.com"
              value={tempBaseUrl}
              onChange={(e) => setTempBaseUrl(e.target.value)}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="api_key">{t('settings.apiKey')}</Label>
            <Input
              id="api_key"
              placeholder="sk-..."
              type="password"
              value={tempApiKey}
              onChange={(e) => setTempApiKey(e.target.value)}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="embed_url">{t('settings.embedUrl')}</Label>
            <Input
              id="embed_url"
              placeholder="http://localhost:11434/v1"
              value={tempEmbedUrl}
              onChange={(e) => setTempEmbedUrl(e.target.value)}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="embed_model">{t('settings.embedModel')}</Label>
            <Input
              id="embed_model"
              placeholder="nomic-embed-text"
              value={tempEmbedModel}
              onChange={(e) => setTempEmbedModel(e.target.value)}
            />
            <p className="text-[11px] text-muted-foreground">{t('settings.embedHint')}</p>
          </div>
          <div className="flex justify-between gap-2 pt-2">
            <Button variant="secondary" type="button" onClick={onReset}>{t('common.reset')}</Button>
            <div className="flex gap-2">
              <Button variant="outline" type="button" onClick={() => setOpen(false)}>{t('common.cancel')}</Button>
              <Button type="button" onClick={onSave}>{t('common.save')}</Button>
            </div>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}
