/**
 * ChatInput Component
 * Message input with model selector and send button
 */

import React, { useState, useRef } from 'react';
import { Send, Sparkles, StopCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { useChatStore } from '@/lib/stores/chatStore';

export function ChatInput() {
  const [input, setInput] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const {
    selectedModel,
    selectedMode,
    isStreaming,
    sendMessage,
    setSelectedModel,
    setSelectedMode,
    _cancelStream,
  } = useChatStore();

  const submitMessage = async () => {
    if (!input.trim() || isStreaming) return;

    await sendMessage(input.trim());
    setInput('');

    // Reset textarea height
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    await submitMessage();
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      submitMessage();
    }
  };

  const handleInput = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value);

    // Auto-resize textarea
    e.target.style.height = 'auto';
    e.target.style.height = `${e.target.scrollHeight}px`;
  };

  return (
    <div className="border-t-2 border-border/60 bg-card/60 p-5 backdrop-blur-xl shadow-[0_-4px_20px_rgba(0,0,0,0.3)]">
      <form onSubmit={handleSubmit} className="space-y-3">
        {/* Model and Mode Selectors */}
        <div className="flex gap-3 mb-1">
          <Select value={selectedModel} onValueChange={setSelectedModel}>
            <SelectTrigger className="w-[200px]">
              <Sparkles size={14} className="mr-2" />
              <SelectValue placeholder="Select model" />
            </SelectTrigger>
            <SelectContent className="max-h-[400px]">
              {/* NAVI Models */}
              <SelectItem value="auto">Auto</SelectItem>
              <SelectItem value="navi-intelligence">NAVI Intelligence</SelectItem>
              <SelectItem value="navi-fast">NAVI Fast</SelectItem>
              <SelectItem value="navi-deep">NAVI Deep</SelectItem>
              <SelectItem value="navi-private">NAVI Private</SelectItem>

              {/* Anthropic Claude */}
              <SelectItem value="claude-sonnet-4">Claude Sonnet 4</SelectItem>
              <SelectItem value="claude-opus-4">Claude Opus 4</SelectItem>
              <SelectItem value="claude-3.5-haiku">Claude 3.5 Haiku</SelectItem>
              <SelectItem value="claude-3.5-sonnet">Claude 3.5 Sonnet</SelectItem>

              {/* OpenAI GPT */}
              <SelectItem value="gpt-5.2">GPT-5.2</SelectItem>
              <SelectItem value="gpt-5.2-pro">GPT-5.2 Pro</SelectItem>
              <SelectItem value="gpt-5.1">GPT-5.1</SelectItem>
              <SelectItem value="gpt-5">GPT-5</SelectItem>
              <SelectItem value="gpt-5-mini">GPT-5 Mini</SelectItem>
              <SelectItem value="gpt-5-nano">GPT-5 Nano</SelectItem>
              <SelectItem value="gpt-4.1">GPT-4.1</SelectItem>
              <SelectItem value="gpt-4.1-mini">GPT-4.1 Mini</SelectItem>
              <SelectItem value="gpt-4o">GPT-4o</SelectItem>
              <SelectItem value="chatgpt-4o-latest">ChatGPT-4o Latest</SelectItem>
              <SelectItem value="gpt-4o-mini">GPT-4o Mini</SelectItem>

              {/* OpenAI o-series */}
              <SelectItem value="o1">o1</SelectItem>
              <SelectItem value="o1-pro">o1 Pro</SelectItem>
              <SelectItem value="o3">o3</SelectItem>
              <SelectItem value="o3-mini">o3 Mini</SelectItem>
              <SelectItem value="o4-mini">o4 Mini</SelectItem>
              <SelectItem value="o4-mini-deep-research">o4 Mini Deep Research</SelectItem>

              {/* Google Gemini */}
              <SelectItem value="gemini-2.5-pro">Gemini 2.5 Pro</SelectItem>
              <SelectItem value="gemini-2.5-flash">Gemini 2.5 Flash</SelectItem>
              <SelectItem value="gemini-2.5-flash-lite">Gemini 2.5 Flash Lite</SelectItem>
              <SelectItem value="gemini-3-pro">Gemini 3 Pro</SelectItem>
            </SelectContent>
          </Select>

          <Select value={selectedMode} onValueChange={(value: any) => setSelectedMode(value)}>
            <SelectTrigger className="w-[140px]">
              <SelectValue placeholder="Mode" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="agent">Agent</SelectItem>
              <SelectItem value="plan">Plan</SelectItem>
              <SelectItem value="ask">Ask</SelectItem>
              <SelectItem value="edit">Edit</SelectItem>
            </SelectContent>
          </Select>
        </div>

        {/* Input Area */}
        <div className="relative flex items-start gap-3">
          <textarea
            ref={textareaRef}
            value={input}
            onChange={handleInput}
            onKeyDown={handleKeyDown}
            placeholder="Ask NAVI anything..."
            disabled={isStreaming}
            className="flex-1 min-h-[100px] max-h-[280px] px-5 py-4 rounded-xl border-2 border-border/80 bg-card/95 text-foreground placeholder:text-muted-foreground/70 resize-none focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/50 focus-visible:border-primary focus-visible:shadow-[0_0_20px_rgba(120,180,255,0.25)] hover:border-border hover:bg-card disabled:opacity-50 disabled:cursor-not-allowed shadow-lg transition-all duration-200 backdrop-blur-sm"
            rows={3}
          />

          {isStreaming ? (
            <Button
              type="button"
              size="icon"
              variant="destructive"
              onClick={_cancelStream}
              className="h-[60px] w-[60px] mt-2 shadow-lg hover:shadow-xl hover:scale-105 transition-all duration-200"
            >
              <StopCircle size={20} />
            </Button>
          ) : (
            <Button
              type="submit"
              size="icon"
              disabled={!input.trim()}
              className="h-[60px] w-[60px] mt-2 shadow-lg hover:shadow-xl hover:scale-105 transition-all duration-200"
            >
              <Send size={20} />
            </Button>
          )}
        </div>

        {/* Helper text */}
        <p className="text-xs text-muted-foreground/60 ml-1 mt-1">
          Press Enter to send, Shift+Enter for new line
        </p>
      </form>
    </div>
  );
}

export default ChatInput;
