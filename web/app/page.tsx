import Link from "next/link";
import { Button } from "@/components/ui/button";
import { ArrowRight, Sparkles, Code, Zap } from "lucide-react";

export default function HomePage() {
  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b border-border bg-card/50 backdrop-blur-sm sticky top-0 z-50">
        <div className="container mx-auto px-4 h-16 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2">
            <div className="h-8 w-8 rounded-lg gradient-ai flex items-center justify-center">
              <span className="text-lg font-bold text-white">N</span>
            </div>
            <span className="text-xl font-bold gradient-ai-text">NAVI</span>
          </Link>

          <div className="flex items-center gap-4">
            <Link
              href="/login"
              className="text-sm text-muted-foreground hover:text-foreground transition-colors"
            >
              Sign In
            </Link>
            <Button asChild size="sm">
              <Link href="/signup">Get Started</Link>
            </Button>
          </div>
        </div>
      </header>

      {/* Hero Section */}
      <main className="container mx-auto px-4 py-24">
        <div className="text-center max-w-3xl mx-auto">
          {/* Badge */}
          <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full border border-primary/30 bg-primary/5 text-primary text-sm mb-8">
            <Sparkles className="h-4 w-4" />
            AI-Powered Engineering Assistant
          </div>

          {/* Headline */}
          <h1 className="text-5xl sm:text-6xl font-bold mb-6">
            Your Intelligent{" "}
            <span className="gradient-ai-text">Pair Programmer</span>
          </h1>

          {/* Subheadline */}
          <p className="text-xl text-muted-foreground mb-8 max-w-2xl mx-auto">
            NAVI understands your codebase, writes production-ready code, and
            helps you ship faster. Like having a senior engineer by your side.
          </p>

          {/* CTA */}
          <div className="flex items-center justify-center gap-4">
            <Button asChild size="lg" className="group">
              <Link href="/signup">
                Start Free
                <ArrowRight className="ml-2 h-4 w-4 group-hover:translate-x-1 transition-transform" />
              </Link>
            </Button>
            <Button asChild variant="outline" size="lg">
              <Link href="/login">Sign In</Link>
            </Button>
          </div>
        </div>

        {/* Features */}
        <div className="grid md:grid-cols-3 gap-8 mt-24">
          <div className="p-6 rounded-xl border border-border bg-card hover:border-primary/50 transition-colors">
            <div className="h-12 w-12 rounded-lg gradient-ai flex items-center justify-center mb-4">
              <Code className="h-6 w-6 text-white" />
            </div>
            <h3 className="text-lg font-semibold mb-2">
              Full Codebase Understanding
            </h3>
            <p className="text-muted-foreground">
              NAVI indexes your entire codebase for deep semantic search and
              context-aware assistance.
            </p>
          </div>

          <div className="p-6 rounded-xl border border-border bg-card hover:border-primary/50 transition-colors">
            <div className="h-12 w-12 rounded-lg gradient-ai flex items-center justify-center mb-4">
              <Zap className="h-6 w-6 text-white" />
            </div>
            <h3 className="text-lg font-semibold mb-2">
              Intelligent Task Planning
            </h3>
            <p className="text-muted-foreground">
              Break down complex features into actionable steps with automatic
              test verification.
            </p>
          </div>

          <div className="p-6 rounded-xl border border-border bg-card hover:border-primary/50 transition-colors">
            <div className="h-12 w-12 rounded-lg gradient-ai flex items-center justify-center mb-4">
              <Sparkles className="h-6 w-6 text-white" />
            </div>
            <h3 className="text-lg font-semibold mb-2">
              Multi-Language Support
            </h3>
            <p className="text-muted-foreground">
              Works with 80+ languages and frameworks including Python, TypeScript,
              Go, Rust, Java, and more.
            </p>
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t border-border py-8 mt-24">
        <div className="container mx-auto px-4 text-center text-sm text-muted-foreground">
          <p>&copy; 2024 NAVI. All rights reserved.</p>
        </div>
      </footer>
    </div>
  );
}
