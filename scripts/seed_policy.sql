-- Seed default organization, users, and policy for development

-- Create default organization
INSERT INTO org (id, name) VALUES ('default', 'Default Organization')
ON CONFLICT (id) DO NOTHING;

-- Create sample users with different roles
INSERT INTO org_user (org_id, user_id, role) VALUES 
('default', 'dev1', 'developer'),
('default', 'lead1', 'maintainer'),
('default', 'admin1', 'admin')
ON CONFLICT DO NOTHING;

-- Remove existing policy if present
DELETE FROM org_policy WHERE org_id='default';

-- Insert default organization policy
INSERT INTO org_policy (
    org_id,
    models_allow,
    phase_budgets,
    commands_allow,
    commands_deny,
    paths_allow,
    repos_allow,
    branches_protected,
    required_reviewers,
    require_review_for
) VALUES (
    'default',
    '["claude-3-5-sonnet-20241022", "gpt-4-turbo", "gpt-4o", "gpt-4.1"]',
    '{"plan":{"tokens":150000,"usd_per_day":5.00},"code":{"tokens":200000,"usd_per_day":8.00},"review":{"tokens":80000,"usd_per_day":2.00}}',
    '["pytest", "npm", "pnpm", "yarn", "mvn", "gradle", "git", "ls", "cat", "grep", "find"]',
    '["docker login", "curl http://", "wget", "rm -rf /", "sudo"]',
    '["backend/**", "web/**", "frontend/**", "src/**", "tests/**", "*.py", "*.ts", "*.tsx", "*.js", "*.jsx"]',
    '["NNDSrinivas/autonomous-engineering-platform"]',
    '["main", "master", "production", "release/*"]',
    1,
    '["git", "pr", "jira"]'
);

-- Display confirmation
SELECT 'Policy seed completed successfully' AS status;
SELECT 'Organizations:' AS info, COUNT(*) AS count FROM org;
SELECT 'Users:' AS info, COUNT(*) AS count FROM org_user;
SELECT 'Policies:' AS info, COUNT(*) AS count FROM org_policy;
