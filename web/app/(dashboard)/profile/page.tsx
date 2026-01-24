import React from "react";
import { getSession } from "@auth0/nextjs-auth0";
import { redirect } from "next/navigation";
import { User, Mail, Building2, Shield, Key, Trash2 } from "lucide-react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";

export const metadata = {
  title: "Profile | NAVI",
  description: "Manage your NAVI profile",
};

export default async function ProfilePage() {
  const session = await getSession();

  if (!session?.user) {
    redirect("/login");
  }

  const user = session.user;
  const roles = (user["https://navralabs.com/roles"] as string[]) || ["viewer"];
  const org = (user["https://navralabs.com/org"] as string) || "public";

  return (
    <div className="max-w-4xl mx-auto space-y-8">
      <div>
        <h1 className="text-3xl font-bold gradient-ai-text">Your Profile</h1>
        <p className="text-muted-foreground mt-2">
          Manage your account settings and preferences
        </p>
      </div>

      {/* Profile Overview */}
      <Card>
        <CardContent className="flex items-center gap-6 p-6">
          {/* Avatar */}
          <div className="relative">
            {user.picture ? (
              <img
                src={user.picture}
                alt={user.name || "User"}
                className="h-20 w-20 rounded-full border-2 border-primary"
              />
            ) : (
              <div className="h-20 w-20 rounded-full bg-secondary flex items-center justify-center border-2 border-primary">
                <User className="h-10 w-10 text-muted-foreground" />
              </div>
            )}
            <div className="absolute -bottom-1 -right-1 h-6 w-6 rounded-full gradient-ai flex items-center justify-center">
              <Shield className="h-3 w-3 text-white" />
            </div>
          </div>

          {/* Info */}
          <div className="flex-1">
            <h2 className="text-xl font-semibold">{user.name || "User"}</h2>
            <p className="text-muted-foreground flex items-center gap-2 mt-1">
              <Mail className="h-4 w-4" />
              {user.email}
            </p>
            <div className="flex gap-2 mt-3">
              {roles.map((role) => (
                <span
                  key={role}
                  className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border border-primary text-primary"
                >
                  {role}
                </span>
              ))}
            </div>
          </div>

          {/* Organization */}
          <div className="text-right">
            <p className="text-sm text-muted-foreground flex items-center justify-end gap-2">
              <Building2 className="h-4 w-4" />
              Organization
            </p>
            <p className="font-medium mt-1">{org}</p>
          </div>
        </CardContent>
      </Card>

      {/* Account Details */}
      <Card>
        <CardHeader>
          <CardTitle>Account Details</CardTitle>
          <CardDescription>
            Your account information from your identity provider
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <label className="text-sm font-medium text-muted-foreground">
                Full Name
              </label>
              <p className="mt-1">{user.name || "Not set"}</p>
            </div>
            <div>
              <label className="text-sm font-medium text-muted-foreground">
                Email Address
              </label>
              <p className="mt-1">{user.email}</p>
            </div>
            <div>
              <label className="text-sm font-medium text-muted-foreground">
                User ID
              </label>
              <p className="mt-1 font-mono text-sm text-muted-foreground">
                {user.sub}
              </p>
            </div>
            <div>
              <label className="text-sm font-medium text-muted-foreground">
                Email Verified
              </label>
              <p className="mt-1">
                {user.email_verified ? (
                  <span className="text-status-success">Verified</span>
                ) : (
                  <span className="text-status-warning">Not verified</span>
                )}
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Security */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Key className="h-5 w-5" />
            Security
          </CardTitle>
          <CardDescription>
            Manage your account security settings
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="font-medium">Change Password</p>
              <p className="text-sm text-muted-foreground">
                Update your password to keep your account secure
              </p>
            </div>
            <Button variant="outline" asChild>
              <a href="/forgot-password">Change Password</a>
            </Button>
          </div>

          <Separator />

          <div className="flex items-center justify-between">
            <div>
              <p className="font-medium">Two-Factor Authentication</p>
              <p className="text-sm text-muted-foreground">
                Add an extra layer of security to your account
              </p>
            </div>
            <Button variant="outline" disabled>
              Configure 2FA
            </Button>
          </div>

          <Separator />

          <div className="flex items-center justify-between">
            <div>
              <p className="font-medium">Active Sessions</p>
              <p className="text-sm text-muted-foreground">
                View and manage your active login sessions
              </p>
            </div>
            <Button variant="outline" disabled>
              View Sessions
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Danger Zone */}
      <Card className="border-destructive/50">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-destructive">
            <Trash2 className="h-5 w-5" />
            Danger Zone
          </CardTitle>
          <CardDescription>
            Irreversible actions that affect your account
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-between">
            <div>
              <p className="font-medium">Delete Account</p>
              <p className="text-sm text-muted-foreground">
                Permanently delete your account and all associated data
              </p>
            </div>
            <Button variant="destructive" disabled>
              Delete Account
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
