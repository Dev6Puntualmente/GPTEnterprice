-- CreateEnum
CREATE TYPE "gptenterprice"."AiServerType" AS ENUM ('VLLM', 'OPENAI_COMPATIBLE');
CREATE TYPE "gptenterprice"."AiProviderRole" AS ENUM ('SMART', 'FAST', 'GENERAL');

-- AlterTable: add document_id nullable first
ALTER TABLE "gptenterprice"."users" ADD COLUMN "document_id" TEXT;
ALTER TABLE "gptenterprice"."users" ALTER COLUMN "email" DROP NOT NULL;

-- Backfill existing users
UPDATE "gptenterprice"."users"
SET "document_id" = '1000000001'
WHERE "document_id" IS NULL;

-- Make document_id required + unique
ALTER TABLE "gptenterprice"."users" ALTER COLUMN "document_id" SET NOT NULL;
CREATE UNIQUE INDEX "users_document_id_key" ON "gptenterprice"."users"("document_id");

-- CreateTable
CREATE TABLE "gptenterprice"."ai_server_configs" (
    "id" TEXT NOT NULL,
    "user_id" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "type" "gptenterprice"."AiServerType" NOT NULL DEFAULT 'VLLM',
    "base_url" TEXT NOT NULL,
    "model_name" TEXT NOT NULL,
    "api_key" TEXT,
    "role" "gptenterprice"."AiProviderRole" NOT NULL DEFAULT 'GENERAL',
    "color" TEXT NOT NULL DEFAULT '#6366f1',
    "enabled" BOOLEAN NOT NULL DEFAULT true,
    "is_default" BOOLEAN NOT NULL DEFAULT false,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "ai_server_configs_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE INDEX "ai_server_configs_user_id_idx" ON "gptenterprice"."ai_server_configs"("user_id");
CREATE INDEX "ai_server_configs_user_id_role_idx" ON "gptenterprice"."ai_server_configs"("user_id", "role");

-- AddForeignKey
ALTER TABLE "gptenterprice"."ai_server_configs" ADD CONSTRAINT "ai_server_configs_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "gptenterprice"."users"("id") ON DELETE CASCADE ON UPDATE CASCADE;
