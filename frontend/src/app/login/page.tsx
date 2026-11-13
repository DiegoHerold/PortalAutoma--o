import { LoginForm } from "@/components/auth/login-form";
import { TelaDeAcesso } from "@/components/auth/tela-de-acesso";

export default function LoginPage() {
  return (
    <TelaDeAcesso titulo="Entrar">
      <LoginForm />
    </TelaDeAcesso>
  );
}
