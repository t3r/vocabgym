<template>
  <div class="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
    <h1 class="text-2xl font-bold text-gray-900 dark:text-white mb-2">Hilfe & Anleitung</h1>
    <p class="text-gray-600 dark:text-gray-400 mb-6">Wähle deine Rolle, um die passende Anleitung zu sehen.</p>

    <!-- Tab Navigation -->
    <div class="flex border-b border-gray-200 dark:border-gray-700 mb-8">
      <button
        @click="activeTab = 'student'"
        class="px-4 py-3 text-sm font-medium border-b-2 transition-colors"
        :class="activeTab === 'student'
          ? 'border-primary-600 text-primary-600 dark:text-primary-400 dark:border-primary-400'
          : 'border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300 hover:border-gray-300'"
      >
        🎓 Für Trainierende
      </button>
      <button
        @click="activeTab = 'teacher'"
        class="px-4 py-3 text-sm font-medium border-b-2 transition-colors"
        :class="activeTab === 'teacher'
          ? 'border-primary-600 text-primary-600 dark:text-primary-400 dark:border-primary-400'
          : 'border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300 hover:border-gray-300'"
      >
        👩‍🏫 Für Lehrende
      </button>
    </div>

    <!-- Student Documentation -->
    <div v-if="activeTab === 'student'" class="prose-content">
      <section class="mb-10">
        <h2 class="section-title">Hey! 👋 Willkommen bei VocabGym</h2>
        <p>VocabGym hilft dir, deine Vokabeln zu lernen — schnell, einfach und ohne nerviges Abtippen von Listen. Deine Lehrkraft scannt die Seiten aus eurem Arbeitsbuch und du kannst direkt losüben. Die App unterstützt Französisch, Englisch, Spanisch und Italienisch.</p>
      </section>

      <section class="mb-10">
        <h2 class="section-title">So funktioniert's</h2>
        <div class="steps">
          <div class="step">
            <span class="step-number">1</span>
            <div>
              <h3 class="step-title">Anmelden & Namen setzen</h3>
              <p>Melde dich mit deiner E-Mail-Adresse an. Klick dann oben rechts auf deinen Namen (oder „Name setzen") und gib dir einen Anzeigenamen — der wird in der Liga-Rangliste angezeigt. Deine E-Mail sieht niemand.</p>
            </div>
          </div>
          <div class="step">
            <span class="step-number">2</span>
            <div>
              <h3 class="step-title">Liga beitreten</h3>
              <p>Deine Lehrkraft gibt dir einen <strong>Beitrittscode</strong> (6 Zeichen). Geh auf „Liga" und gib den Code ein — schon bist du dabei!</p>
            </div>
          </div>
          <div class="step">
            <span class="step-number">3</span>
            <div>
              <h3 class="step-title">Üben</h3>
              <p>Du findest die Vokabelsets zum Üben an zwei Stellen: auf deinem <strong>Dashboard</strong> unter „Liga-Vokabeln" und direkt in der <strong>Liga-Ansicht</strong> unter „Jetzt üben". Klick auf „Üben" und leg los!</p>
            </div>
          </div>
          <div class="step">
            <span class="step-number">4</span>
            <div>
              <h3 class="step-title">Punkte sammeln & Streak halten</h3>
              <p>Jede richtige Antwort bringt dir Punkte für die Liga-Rangliste. Wenn du <strong>jeden Tag</strong> übst, wächst dein 🔥 Streak — miss keinen Tag, sonst geht er auf null! Nach jeder Übung siehst du, wie viele Punkte du für die Liga gesammelt hast.</p>
            </div>
          </div>
        </div>
      </section>

      <section class="mb-10">
        <h2 class="section-title">Tipps zum Üben</h2>
        <div class="tips-grid">
          <div class="tip-card">
            <span class="tip-icon">💡</span>
            <h3>Tippfehler?</h3>
            <p>Kleine Tippfehler (1-2 Zeichen daneben) werden erkannt — du bekommst dann die Chance, deine Antwort zu bestätigen oder zu korrigieren.</p>
          </div>
          <div class="tip-card">
            <span class="tip-icon">🎯</span>
            <h3>Artikel beachten!</h3>
            <p>Pass bei den Artikeln auf! Falscher Artikel = leider falsch. Aber du bekommst eine Erklärung zum Geschlecht angezeigt.</p>
          </div>
          <div class="tip-card">
            <span class="tip-icon">⏭️</span>
            <h3>Überspringen</h3>
            <p>Keine Ahnung? Kein Stress — du kannst Vokabeln überspringen. Sie kommen dann am Ende nochmal dran.</p>
          </div>
          <div class="tip-card">
            <span class="tip-icon">🔥</span>
            <h3>Vorsagen & neue Wörter</h3>
            <p>Bei einem <strong>neuen Wort</strong>, das du noch nie richtig hattest, kannst du dir die Lösung sofort zeigen und vorsprechen lassen. Bei bekannten Wörtern wird der Vorsagen-Button nach 2 richtigen Antworten in Folge freigeschaltet.</p>
          </div>
          <div class="tip-card">
            <span class="tip-icon">🔊</span>
            <h3>Aussprache anhören</h3>
            <p>Neben dem Fremdsprach-Wort im Feedback findest du ein Lautsprecher-Symbol. Klick darauf, um die Aussprache zu hören. Über das kleine Pfeil-Symbol kannst du <strong>Akzent</strong> (z.B. britisches oder amerikanisches Englisch) und <strong>Stimme</strong> wählen — deine Wahl wird gemerkt.</p>
          </div>
          <div class="tip-card">
            <span class="tip-icon">📊</span>
            <h3>Fortschritt</h3>
            <p>Unter „Fortschritt" siehst du, welche Vokabeln du schon drauf hast und welche noch Übung brauchen.</p>
          </div>
          <div class="tip-card">
            <span class="tip-icon">🏆</span>
            <h3>Liga-Rangliste</h3>
            <p>Unter „Liga" siehst du, wie du im Vergleich zu den anderen stehst. Wer hat den längsten Streak? Wer die meisten Punkte?</p>
          </div>
        </div>
      </section>

      <section class="mb-10">
        <h2 class="section-title">Mehrere Antworten möglich?</h2>
        <p>Manchmal gibt es mehr als eine richtige Übersetzung. Wenn mehrere Antworten hinterlegt sind (getrennt durch „;"), wird jede davon akzeptiert. Du musst nur <strong>eine</strong> davon richtig eintippen.</p>
      </section>

      <section class="mb-10">
        <h2 class="section-title">Übungsrichtung wählen</h2>
        <p>Vor jeder Übung kannst du die Richtung wählen: „Deutsch → Zielsprache" oder „Zielsprache → Deutsch". Wechsle ab, damit du in beide Richtungen fit wirst!</p>
      </section>

      <section class="mb-10">
        <h2 class="section-title">Lernziele 🎯</h2>
        <p>Ein Lernziel bündelt ein oder mehrere Vokabelsets mit einer <strong>Deadline</strong> und einem Ziel-Level (wie gut du die Wörter beherrschen sollst). Auf dem Dashboard siehst du dein aktuelles Ziel mit Fortschrittsbalken und einem Hinweis, wie viele Wörter du pro Tag üben solltest, um es rechtzeitig zu schaffen. Deine Lehrkraft kann der ganzen Liga ein gemeinsames Ziel setzen — oder du legst dir selbst eins an.</p>
      </section>

      <section class="mb-10">
        <h2 class="section-title">Dark Mode 🌙</h2>
        <p>Augen müde? Klick oben rechts auf das Mond-Symbol (🌙), um in den dunklen Modus zu wechseln. Nochmal klicken (☀️) bringt dich zurück.</p>
      </section>

      <section>
        <h2 class="section-title">Probleme?</h2>
        <p>Falls etwas nicht funktioniert, wird dir eine Fehlermeldung mit einer <strong>Fehler-ID</strong> angezeigt (z.B. „Fehler: a3f2b1c8"). Gib diese ID an deine Lehrkraft weiter — damit kann das Problem schneller gefunden werden.</p>
      </section>
    </div>

    <!-- Teacher Documentation -->
    <div v-if="activeTab === 'teacher'" class="prose-content">
      <section class="mb-10">
        <h2 class="section-title">Willkommen, VocabGym für Lehrkräfte</h2>
        <p>VocabGym unterstützt Sie dabei, Ihren Schülerinnen und Schülern eine motivierende Lernumgebung für Vokabeln bereitzustellen. Sie scannen die Arbeitsbuchseiten, die App extrahiert die Vokabeln automatisch per KI, und Ihre Klasse kann sofort üben. Unterstützte Zielsprachen: Französisch, Englisch, Spanisch und Italienisch.</p>
      </section>

      <section class="mb-10">
        <h2 class="section-title">Erste Schritte</h2>
        <div class="steps">
          <div class="step">
            <span class="step-number">1</span>
            <div>
              <h3 class="step-title">Konto einrichten</h3>
              <p>Registrieren Sie sich mit Ihrer E-Mail-Adresse. Ihre Lehrkraft-Rolle wird vom Administrator freigeschaltet (Cognito-Gruppe „teachers"). Setzen Sie anschließend Ihren Anzeigenamen über den Klick auf Ihren Namen oben rechts.</p>
            </div>
          </div>
          <div class="step">
            <span class="step-number">2</span>
            <div>
              <h3 class="step-title">Liga erstellen</h3>
              <p>Navigieren Sie zu „Liga" und erstellen Sie eine neue Liga für Ihre Klasse. Wählen Sie einen Namen und den gewünschten Score-Modus (siehe unten). Sie erhalten einen 6-stelligen Beitrittscode, den Sie Ihren Schülerinnen und Schülern mitteilen.</p>
            </div>
          </div>
          <div class="step">
            <span class="step-number">3</span>
            <div>
              <h3 class="step-title">Vokabeln hochladen</h3>
              <p>Fotografieren Sie die Vokabelseiten und laden Sie diese unter „Hochladen" hoch. Wählen Sie dabei die <strong>Zielsprache</strong>. Sie können mehrere Seiten gleichzeitig hochladen — sie werden automatisch einem Set zugeordnet. Die KI erkennt die Vokabelpaare und bereinigt das Ergebnis automatisch (entfernt Überschriften, Seitenzahlen etc.).</p>
            </div>
          </div>
          <div class="step">
            <span class="step-number">4</span>
            <div>
              <h3 class="step-title">Vokabeln prüfen</h3>
              <p>Nach dem Upload sehen Sie alle hochgeladenen Bilder mit den zugeordneten Vokabeln darunter. Korrigieren oder löschen Sie fehlerhafte Einträge direkt inline. Fügen Sie fehlende Paare manuell hinzu.</p>
            </div>
          </div>
          <div class="step">
            <span class="step-number">5</span>
            <div>
              <h3 class="step-title">Vokabelsets der Liga zuweisen</h3>
              <p>In der Liga-Verwaltung können Sie festlegen, welche Vokabelsets für die Klasse freigeschaltet werden. Nur zugewiesene Sets erscheinen bei den Lernenden.</p>
            </div>
          </div>
        </div>
      </section>

      <section class="mb-10">
        <h2 class="section-title">Vokabeln hochladen & prüfen</h2>
        <div class="info-box">
          <h3 class="font-semibold mb-2">Tipps für optimale Erkennung:</h3>
          <ul class="list-disc list-inside space-y-1 text-sm">
            <li>Fotografieren Sie die Seite bei gutem Licht, möglichst gerade</li>
            <li>Unterstützte Formate: JPG, PNG (max. 10 MB) — HEIC-Fotos vom iPhone werden automatisch konvertiert</li>
            <li>Tabellenstrukturen werden am besten erkannt</li>
            <li>Mehrere Seiten können gleichzeitig hochgeladen werden</li>
            <li>Die KI bereinigt automatisch: Phonetik [eckige Klammern], Überschriften, Nicht-Vokabel-Einträge</li>
            <li>Seiten ohne echte Vokabelpaare (z.B. Grammatik-Erklärungen) werden automatisch als leer erkannt</li>
          </ul>
        </div>
        <p class="mt-4">Im Prüfbildschirm sehen Sie jedes hochgeladene Bild mit den zugeordneten Vokabeln darunter. Sie können:</p>
        <ul class="list-disc list-inside space-y-1 mt-2 text-gray-700 dark:text-gray-300">
          <li>Einzelne Einträge inline korrigieren</li>
          <li>Vokabeln per ✕-Button löschen</li>
          <li>Neue Paare pro Bild hinzufügen</li>
          <li>Titel und Metadaten (Kapitel, Seite, Thema) setzen</li>
        </ul>
      </section>

      <section class="mb-10">
        <h2 class="section-title">Score-Modi</h2>
        <p class="mb-4">Beim Erstellen der Liga wählen Sie, wie die Rangliste berechnet wird:</p>
        <div class="grid gap-3">
          <div class="mode-card">
            <h3 class="font-semibold">Gesamtzahl Richtige</h3>
            <p class="text-sm text-gray-600 dark:text-gray-400">Wer insgesamt die meisten richtigen Antworten hat, steht oben. Belohnt Fleiß und regelmäßiges Üben.</p>
          </div>
          <div class="mode-card">
            <h3 class="font-semibold">Wöchentlich</h3>
            <p class="text-sm text-gray-600 dark:text-gray-400">Die Rangliste wird jeden Montag zurückgesetzt. Jede Woche beginnt ein neuer Wettbewerb — ideal, um auch Nachzügler zu motivieren.</p>
          </div>
          <div class="mode-card">
            <h3 class="font-semibold">Genauigkeit</h3>
            <p class="text-sm text-gray-600 dark:text-gray-400">Sortiert nach dem Anteil richtiger Antworten (Prozent). Belohnt Qualität statt Quantität.</p>
          </div>
          <div class="mode-card">
            <h3 class="font-semibold">Kombiniert</h3>
            <p class="text-sm text-gray-600 dark:text-gray-400">Richtige Antworten × Streak-Bonus. Belohnt sowohl Wissen als auch Konstanz.</p>
          </div>
        </div>
        <p class="mt-4 text-sm text-gray-500 dark:text-gray-400">Der Score-Modus kann jederzeit in der Liga-Verwaltung geändert werden.</p>
      </section>

      <section class="mb-10">
        <h2 class="section-title">Liga verwalten</h2>
        <p>In der Liga-Ansicht finden Sie als Lehrkraft folgende Verwaltungsmöglichkeiten:</p>
        <ul class="list-disc list-inside space-y-2 mt-3 text-gray-700 dark:text-gray-300">
          <li><strong>Beitrittscode</strong> — Teilen Sie diesen Code mit Ihrer Klasse (z.B. an die Tafel schreiben, per Chat senden). Per Klick kopierbar.</li>
          <li><strong>Score-Modus</strong> — Jederzeit änderbar per Dropdown</li>
          <li><strong>Vokabelsets zuweisen</strong> — Aktivieren Sie per Checkbox die Sets, die geübt werden sollen</li>
          <li><strong>Teilnehmer-Details</strong> — Klicken Sie auf einen Teilnehmer für detaillierte Statistiken (Genauigkeit, wöchentlicher Score, Gesamtversuche, letztes Übungsdatum)</li>
          <li><strong>Teilnehmer entfernen</strong> — In der Detailansicht eines Teilnehmers</li>
        </ul>
      </section>

      <section class="mb-10">
        <h2 class="section-title">Lernziele für die Liga</h2>
        <p>Sie können Ihrer Liga ein gemeinsames <strong>Lernziel</strong> zuweisen: ein oder mehrere Vokabelsets, eine Deadline und ein Ziel-Mastery-Level (3–5). Die App berechnet pro Lernendem den Fortschritt, das Tempo und einen Status (im Zeitplan, gefährdet, im Rückstand, abgelaufen oder geschafft). In der Ziel-Detailansicht sehen Sie den Fortschritt aller Mitglieder auf einen Blick — ideal, um rechtzeitig nachzusteuern.</p>
      </section>

      <section class="mb-10">
        <h2 class="section-title">Aussprache (Text-to-Speech)</h2>
        <p>Beim Üben können die Lernenden sich das Fremdsprach-Wort vorlesen lassen (Amazon Polly). Akzent (z.B. britisches/amerikanisches Englisch) und Stimme sind wählbar. Für neue Wörter, die noch nie richtig beantwortet wurden, wird die Lösung sofort angeboten und vorgesprochen — so können die Lernenden ein unbekanntes Wort direkt korrekt hören. Es wird ausschließlich die Zielsprache vorgelesen.</p>
      </section>

      <section class="mb-10">
        <h2 class="section-title">Ergebnisse einsehen</h2>
        <p>Klicken Sie in der Teilnehmer-Liste auf einen Namen, um die Detailansicht aufzuklappen:</p>
        <ul class="list-disc list-inside space-y-1 mt-2 text-gray-700 dark:text-gray-300">
          <li>Gesamt richtige Antworten und Gesamtversuche</li>
          <li>Genauigkeit in Prozent</li>
          <li>Wöchentlicher Score (aktuelle Woche)</li>
          <li>Aktueller Streak (aufeinanderfolgende Übungstage)</li>
          <li>Datum der letzten Übung und Beitrittsdatum</li>
        </ul>
        <p class="mt-3 text-sm text-gray-500 dark:text-gray-400">Hinweis: Die Lernenden sehen untereinander nur die Rangliste (Anzeigename, Punktzahl, Streak), nicht die detaillierten Ergebnisse der anderen. E-Mail-Adressen werden nirgends angezeigt.</p>
      </section>

      <section class="mb-10">
        <h2 class="section-title">Streak-System</h2>
        <p>Der Streak zählt aufeinanderfolgende Kalendertage, an denen geübt wurde. Wird an einem Tag nicht geübt, wird der Streak auf 0 zurückgesetzt. Dies motiviert die Lernenden zu täglicher, kurzer Übungspraxis. Die Lernenden sehen ihren Streak im Dashboard und in der Liga-Ansicht.</p>
      </section>

      <section class="mb-10">
        <h2 class="section-title">Anzeigenamen</h2>
        <p>Alle Teilnehmenden setzen ihren eigenen Anzeigenamen (Klick auf den Namen oben rechts). Nur dieser Name erscheint in der Liga — E-Mail-Adressen werden niemals anderen Teilnehmenden angezeigt. Ermutigen Sie Ihre Klasse, einen erkennbaren Namen zu wählen.</p>
      </section>

      <section>
        <h2 class="section-title">Fehlerbehebung</h2>
        <div class="info-box">
          <p>Bei Fehlermeldungen wird eine eindeutige <strong>Fehler-ID</strong> angezeigt (z.B. „a3f2b1c8"). Diese ID identifiziert den Fehler in den Server-Logs und erleichtert die Diagnose erheblich.</p>
        </div>
        <div class="mt-4 space-y-3">
          <div>
            <h3 class="font-semibold text-gray-900 dark:text-white">Vokabeln werden nicht korrekt erkannt</h3>
            <p class="text-sm text-gray-600 dark:text-gray-400">Stellen Sie sicher, dass das Foto scharf ist und die Tabelle gut lesbar. Die KI filtert automatisch Nicht-Vokabel-Inhalte, aber bei ungewöhnlichen Layouts kann es zu Fehlern kommen. Korrigieren Sie im Prüfbildschirm.</p>
          </div>
          <div>
            <h3 class="font-semibold text-gray-900 dark:text-white">Seite wird als „leer" erkannt</h3>
            <p class="text-sm text-gray-600 dark:text-gray-400">Seiten ohne echte Vokabelpaare (z.B. reine Grammatik-Erklärungen, Übungsanweisungen) werden von der KI korrekt als nicht verwendbar erkannt. Scannen Sie nur Seiten mit Vokabeltabellen.</p>
          </div>
          <div>
            <h3 class="font-semibold text-gray-900 dark:text-white">Schüler/in kann nicht beitreten</h3>
            <p class="text-sm text-gray-600 dark:text-gray-400">Jede Person kann nur einer Liga angehören. Prüfen Sie, ob die Person eventuell bereits Mitglied einer anderen Liga ist.</p>
          </div>
          <div>
            <h3 class="font-semibold text-gray-900 dark:text-white">Liga-Scores werden nicht aktualisiert</h3>
            <p class="text-sm text-gray-600 dark:text-gray-400">Scores werden nach jeder abgeschlossenen Übung aktualisiert. Stellen Sie sicher, dass die Übung vollständig beendet wird (nicht vorzeitig geschlossen).</p>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const activeTab = ref('student')
</script>

<style scoped>
.prose-content p {
  @apply text-gray-700 dark:text-gray-300 leading-relaxed;
}

.section-title {
  @apply text-xl font-semibold text-gray-900 dark:text-white mb-3;
}

.steps {
  @apply space-y-4;
}

.step {
  @apply flex gap-4 items-start;
}

.step-number {
  @apply flex-shrink-0 w-8 h-8 bg-primary-600 text-white rounded-full flex items-center justify-center text-sm font-bold;
}

.step-title {
  @apply font-semibold text-gray-900 dark:text-white mb-1;
}

.step p {
  @apply text-sm text-gray-600 dark:text-gray-400;
}

.tips-grid {
  @apply grid grid-cols-1 sm:grid-cols-2 gap-4;
}

.tip-card {
  @apply p-4 bg-gray-50 dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700;
}

.tip-card h3 {
  @apply font-semibold text-gray-900 dark:text-white text-sm mb-1;
}

.tip-card p {
  @apply text-xs text-gray-600 dark:text-gray-400;
}

.tip-icon {
  @apply text-2xl mb-2 block;
}

.info-box {
  @apply p-4 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg text-gray-700 dark:text-gray-300;
}

.mode-card {
  @apply p-3 bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg;
}

.mode-card h3 {
  @apply text-gray-900 dark:text-white;
}
</style>
