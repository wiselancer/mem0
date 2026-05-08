/**
 * Public Artifacts Provider for OpenClaw memory-wiki bridge mode.
 *
 * Exposes Mem0 memories and dream state as artifacts that can be
 * consumed by other plugins (e.g., memory-wiki in bridge mode).
 */

import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import type { Mem0Provider, MemoryItem, Mem0Config } from "./types.ts";
import type { MemoryArtifact } from "openclaw/plugin-sdk";
import { getDreamState } from "./dream-gate.ts";

export interface PublicArtifactsContext {
  provider: Mem0Provider;
  cfg: Mem0Config;
  stateDir?: string;
  effectiveUserId: (sessionKey?: string) => string;
}

/**
 * Create a publicArtifacts provider that exposes Mem0 data to other plugins.
 */
export function createPublicArtifactsProvider(ctx: PublicArtifactsContext) {
  return {
    async listArtifacts(options?: {
      userId?: string;
      types?: string[];
      limit?: number;
    }): Promise<MemoryArtifact[]> {
      const userId = options?.userId ?? ctx.effectiveUserId();
      const types = options?.types ?? ["memory", "dream", "entity"];
      const limit = options?.limit ?? 100;
      const artifacts: MemoryArtifact[] = [];

      try {
        const stateDir = ctx.stateDir ?? process.env.OPENCLAW_STATE_DIR;
        if (!stateDir) {
          return artifacts;
        }

        const publicDir = path.join(stateDir, "mem0-public-artifacts");
        await mkdir(publicDir, { recursive: true });

        // Memory artifacts
        if (types.includes("memory")) {
          const memories = await ctx.provider.getAll({
            user_id: userId,
            page_size: limit,
          });

          const memoryArtifact = await writeMemoryRootArtifact({
            publicDir,
            userId,
            memories,
          });
          artifacts.push(memoryArtifact);
        }

        // Dream state artifact (if dream enabled and stateDir available)
        if (types.includes("dream") && ctx.cfg.skills?.dream?.enabled) {
          const dreamArtifact = await writeDreamArtifact({
            publicDir,
            stateDir,
            userId,
          });
          if (dreamArtifact) {
            artifacts.push(dreamArtifact);
          }
        }

      } catch (err) {
        console.warn(
          "[mem0] publicArtifacts.listArtifacts failed:",
          err instanceof Error ? err.message : err,
        );
      }

      return artifacts.slice(0, limit);
    },
  };
}

/**
 * Write a file-backed memory root artifact for OpenClaw memory-wiki bridge mode.
 */
async function writeMemoryRootArtifact(params: {
  publicDir: string;
  userId: string;
  memories: MemoryItem[];
}): Promise<MemoryArtifact> {
  const absolutePath = path.join(params.publicDir, "mem0-memory-root.md");
  const relativePath = "memory/mem0-memory-root.md";
  const sortedMemories = [...params.memories].sort((left, right) => {
    const leftKey = left.updated_at ?? left.created_at ?? "";
    const rightKey = right.updated_at ?? right.created_at ?? "";
    if (rightKey !== leftKey) return rightKey.localeCompare(leftKey);
    return left.id.localeCompare(right.id);
  });
  const content = [
    "# Mem0 Memory Root",
    "",
    `User: ${params.userId}`,
    `Exported: ${new Date().toISOString()}`,
    `Memory count: ${sortedMemories.length}`,
    "",
    ...sortedMemories.flatMap((mem) => formatMemoryMarkdown(mem)),
  ].join("\n");

  await writeFile(absolutePath, content, "utf8");

  return {
    id: `mem0:memory-root:${params.userId}`,
    type: "memory",
    title: "Mem0 Memory Root",
    content,
    kind: "memory-root",
    contentType: "text/markdown",
    workspaceDir: params.publicDir,
    relativePath,
    absolutePath,
    agentIds: [],
    userIds: [params.userId],
    sourceIds: sortedMemories.map((mem) => `mem0:memory:${mem.id}`),
    tags: ["mem0", "memory-root"],
    metadata: {
      user_id: params.userId,
      memoryCount: sortedMemories.length,
    },
    updatedAt: new Date().toISOString(),
  };
}

/**
 * Get dream consolidation state as an artifact.
 */
async function writeDreamArtifact(params: {
  publicDir: string;
  stateDir: string;
  userId: string;
}): Promise<MemoryArtifact | null> {
  try {
    const state = getDreamState(params.stateDir);
    if (state.lastConsolidatedAt === 0) {
      return null; // No consolidation has occurred yet
    }

    const lastDate = new Date(state.lastConsolidatedAt).toISOString();
    const absolutePath = path.join(params.publicDir, "mem0-dream-state.md");
    const relativePath = "memory/mem0-dream-state.md";
    const content = [
      "# Mem0 Dream State",
      "",
      `Last consolidation: ${lastDate}`,
      `Sessions since: ${state.sessionsSince}`,
      `Last session: ${state.lastSessionId ?? "none"}`,
      "",
    ].join("\n");
    await writeFile(absolutePath, content, "utf8");

    return {
      id: `mem0:dream:${params.userId}:state`,
      type: "dream",
      title: `Dream State (last: ${lastDate.split("T")[0]})`,
      content,
      kind: "dream-report",
      contentType: "text/markdown",
      workspaceDir: params.publicDir,
      relativePath,
      absolutePath,
      agentIds: [],
      userIds: [params.userId],
      sourceIds: ["mem0:dream-state"],
      tags: ["dream", "mem0"],
      metadata: {
        lastConsolidatedAt: state.lastConsolidatedAt,
        sessionsSince: state.sessionsSince,
        lastSessionId: state.lastSessionId,
        user_id: params.userId,
      },
      updatedAt: lastDate,
    };
  } catch {
    return null;
  }
}

function formatMemoryMarkdown(mem: MemoryItem): string[] {
  const categories = Array.isArray(mem.categories) && mem.categories.length > 0 ? mem.categories.join(", ") : "uncategorized";
  return [
    `## ${mem.id}`,
    "",
    mem.memory,
    "",
    `- Categories: ${categories}`,
    mem.created_at ? `- Created: ${mem.created_at}` : null,
    mem.updated_at ? `- Updated: ${mem.updated_at}` : null,
    "",
  ].filter((line): line is string => typeof line === "string");
}
