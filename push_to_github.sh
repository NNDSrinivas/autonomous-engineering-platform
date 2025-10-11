#!/bin/bash

echo "🚀 Pushing Autonomous Engineering Platform to GitHub..."
echo "Repository: https://github.com/NNDSrinivas/autonomous-engineering-platform"
echo ""

# Ensure we're on main branch
git branch -M main

# Push to GitHub
echo "📤 Pushing to origin/main..."
git push -u origin main

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Successfully pushed to GitHub!"
    echo "🌐 Your repository is now available at:"
    echo "   https://github.com/NNDSrinivas/autonomous-engineering-platform"
    echo ""
    echo "🔗 Next steps:"
    echo "   1. Visit your repository on GitHub"
    echo "   2. Add any additional collaborators"
    echo "   3. Configure branch protection rules (optional)"
    echo "   4. Set up GitHub Actions (optional)"
else
    echo ""
    echo "❌ Push failed. Please check:"
    echo "   1. Repository exists on GitHub"
    echo "   2. You have push permissions"
    echo "   3. Your GitHub credentials are configured"
fi
