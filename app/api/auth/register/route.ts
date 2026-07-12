import { NextResponse } from "next/server";
import bcrypt from "bcryptjs";
import { prisma } from "@/lib/prisma";

/** Registro público solo cuando no hay ningún admin (bootstrap inicial) */
export async function POST(req: Request) {
  try {
    const body = (await req.json()) as {
      documentId?: string;
      password?: string;
      name?: string;
    };
    const documentId = body.documentId?.trim().replace(/\D/g, "") ?? "";
    const password = body.password ?? "";
    const name = body.name?.trim();

    if (!documentId || documentId.length < 6 || password.length < 8) {
      return NextResponse.json(
        { error: "Documento (mín. 6 dígitos) y contraseña (mín. 8) requeridos" },
        { status: 400 },
      );
    }

    const adminCount = await prisma.user.count({ where: { role: "ADMIN" } });
    if (adminCount > 0) {
      return NextResponse.json(
        { error: "El registro está cerrado. Contacta a un administrador." },
        { status: 403 },
      );
    }

    const exists = await prisma.user.findUnique({ where: { documentId } });
    if (exists) {
      return NextResponse.json({ error: "El documento ya está registrado" }, { status: 409 });
    }

    const passwordHash = await bcrypt.hash(password, 12);
    const user = await prisma.user.create({
      data: {
        documentId,
        name: name || null,
        passwordHash,
        role: "ADMIN",
      },
      select: { id: true, documentId: true, name: true, role: true },
    });

    return NextResponse.json(user, { status: 201 });
  } catch {
    return NextResponse.json({ error: "Error interno" }, { status: 500 });
  }
}
