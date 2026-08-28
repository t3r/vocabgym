<template>
  <div class="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-8 prose-dsgvo">
    <h1 class="text-2xl font-bold text-gray-900 dark:text-white mb-2">Datenschutzerklärung</h1>
    <p class="text-sm text-gray-500 dark:text-gray-400 mb-8">Stand: {{ lastUpdated }}</p>

    <section>
      <h2>1. Verantwortlicher</h2>
      <p>
        Verantwortlicher im Sinne der Datenschutz-Grundverordnung (DSGVO) ist:
      </p>
      <p class="placeholder">
        [Name / Einrichtung]<br />
        [Straße und Hausnummer]<br />
        [PLZ und Ort]<br />
        E-Mail: [kontakt@example.org]
      </p>
      <p class="note">
        Hinweis für den Betreiber: Bitte tragen Sie hier die vollständigen
        Kontaktdaten des Verantwortlichen ein. Sofern eine Schule oder ein
        Schulträger verantwortlich ist, sind zusätzlich die Kontaktdaten der
        oder des Datenschutzbeauftragten anzugeben.
      </p>
    </section>

    <section>
      <h2>2. Überblick</h2>
      <p>
        VocabGym ist eine Web-Anwendung zum Vokabeltraining. Nachfolgend
        informieren wir darüber, welche personenbezogenen Daten wir bei der
        Nutzung verarbeiten, zu welchem Zweck und auf welcher Rechtsgrundlage.
        Die gesamte Verarbeitung findet auf Servern von Amazon Web Services
        (AWS) in der Region Frankfurt am Main (eu-central-1) statt.
      </p>
    </section>

    <section>
      <h2>3. Bereitstellung der Anwendung (Hosting &amp; Auslieferung)</h2>
      <p>
        Die Anwendung wird über das Content Delivery Network Amazon CloudFront
        aus einem Amazon-S3-Speicher ausgeliefert. Beim Aufruf werden technisch
        notwendige Zugriffsdaten (u. a. IP-Adresse, Datum und Uhrzeit,
        angeforderte Datei, Browsertyp) verarbeitet, um die Auslieferung zu
        ermöglichen und die Sicherheit zu gewährleisten.
      </p>
      <ul>
        <li><strong>Zweck:</strong> Auslieferung und Betrieb der Anwendung, IT-Sicherheit</li>
        <li><strong>Rechtsgrundlage:</strong> Art. 6 Abs. 1 lit. f DSGVO (berechtigtes Interesse an einem sicheren, funktionsfähigen Angebot)</li>
      </ul>
      <p>
        Schriftarten (Schriftfamilie „Inter") werden ausschließlich von unserem
        eigenen Server ausgeliefert. Es werden <strong>keine</strong> externen
        Dienste wie Google Fonts eingebunden; es findet somit keine Übertragung
        Ihrer IP-Adresse an Dritte zum Laden von Schriften statt.
      </p>
    </section>

    <section>
      <h2>4. Registrierung und Anmeldung (Konto)</h2>
      <p>
        Die Anmeldung erfolgt über Amazon Cognito. Konten werden ausschließlich
        durch eine Lehrkraft per Einladung erstellt (kein offener
        Selbst-Registrierungsprozess). Verarbeitet werden:
      </p>
      <ul>
        <li>E-Mail-Adresse (zur Anmeldung und Kontowiederherstellung)</li>
        <li>Ein selbst gewählter Anzeigename</li>
        <li>Rolle (Schüler:in oder Lehrkraft)</li>
        <li>Authentifizierungs-Metadaten (Zeitpunkt der letzten Anmeldung)</li>
      </ul>
      <ul>
        <li><strong>Zweck:</strong> Bereitstellung des Nutzerkontos, Authentifizierung, Rollenverwaltung</li>
        <li><strong>Rechtsgrundlage:</strong> Art. 6 Abs. 1 lit. b DSGVO (Erfüllung des Nutzungsverhältnisses); bei schulischer Nutzung ggf. Art. 6 Abs. 1 lit. e DSGVO i. V. m. dem jeweiligen Landesschulrecht</li>
      </ul>
      <p>
        Die E-Mail-Adresse wird anderen Nutzenden <strong>zu keinem Zeitpunkt</strong>
        angezeigt. In Ranglisten und Mitgliederlisten erscheint ausschließlich
        der Anzeigename.
      </p>
    </section>

    <section>
      <h2>5. Hochgeladene Bilder &amp; Vokabel-Extraktion</h2>
      <p>
        Lehrkräfte laden Fotos von Arbeitsbuchseiten hoch. Diese werden in
        Amazon S3 gespeichert und zur automatischen Erkennung von Vokabelpaaren
        an folgende AWS-Dienste übergeben:
      </p>
      <ul>
        <li>Amazon Textract (Texterkennung/OCR)</li>
        <li>Amazon Bedrock (Modell „Amazon Nova Pro") zur Extraktion der Vokabelpaare aus dem erkannten Text</li>
      </ul>
      <ul>
        <li><strong>Zweck:</strong> Automatische Erstellung von Vokabelsets aus Arbeitsbuchseiten</li>
        <li><strong>Rechtsgrundlage:</strong> Art. 6 Abs. 1 lit. b bzw. lit. e DSGVO</li>
        <li><strong>Speicherdauer:</strong> Hochgeladene Bilder werden automatisch nach 90 Tagen gelöscht.</li>
      </ul>
      <p class="note">
        Hinweis: Es sollten keine personenbezogenen Daten Dritter auf den
        hochgeladenen Seiten enthalten sein. Bitte laden Sie ausschließlich
        Vokabelseiten hoch.
      </p>
    </section>

    <section>
      <h2>6. Übungsdaten &amp; Fortschritt</h2>
      <p>Zur Bereitstellung der Lernfunktionen verarbeiten wir:</p>
      <ul>
        <li>Vokabelsets und einzelne Vokabeln (Quell- und Zielwort)</li>
        <li>Übungssitzungen (Ergebnisse, Dauer, Zeitpunkt)</li>
        <li>Lernfortschritt je Vokabel (richtige/falsche Antworten, Beherrschungsgrad, zuletzt gegebene Fehlantworten zur Fehleranalyse)</li>
        <li>Lernziele mit Frist und Zielniveau</li>
      </ul>
      <ul>
        <li><strong>Zweck:</strong> Durchführung des Vokabeltrainings, Fortschrittsanzeige, personalisierte Lernhinweise (Smart Repetition)</li>
        <li><strong>Rechtsgrundlage:</strong> Art. 6 Abs. 1 lit. b bzw. lit. e DSGVO</li>
        <li><strong>Speicherdauer:</strong> Übungssitzungen werden automatisch nach 90 Tagen gelöscht; Fortschritts- und Vokabeldaten bis zur Löschung des Kontos bzw. des jeweiligen Vokabelsets.</li>
      </ul>
    </section>

    <section>
      <h2>7. Liga-System</h2>
      <p>
        Lehrkräfte können „Ligen" (Lerngruppen) erstellen; Lernende treten mit
        einem Code bei. In der Liga werden Anzeigename, Punktzahl und Streak
        (aufeinanderfolgende Übungstage) verarbeitet und in einer Rangliste
        angezeigt.
      </p>
      <ul>
        <li><strong>Zweck:</strong> Gruppenverwaltung und motivierende Rangliste</li>
        <li><strong>Rechtsgrundlage:</strong> Art. 6 Abs. 1 lit. b bzw. lit. e DSGVO</li>
      </ul>
    </section>

    <section>
      <h2>8. Aussprache (Text-to-Speech)</h2>
      <p>
        Auf Anforderung wird ein Vokabelwort mit Amazon Polly in Sprache
        umgewandelt. Übertragen wird ausschließlich das jeweilige Zielwort (kein
        personenbezogener Inhalt). Die erzeugte Audiodatei wird zur
        Kostenreduktion zwischengespeichert und nach 30 Tagen automatisch
        gelöscht.
      </p>
      <ul>
        <li><strong>Zweck:</strong> Vorlesen der Aussprache</li>
        <li><strong>Rechtsgrundlage:</strong> Art. 6 Abs. 1 lit. b DSGVO</li>
      </ul>
    </section>

    <section>
      <h2>9. Lokale Speicherung (localStorage)</h2>
      <p>
        Zur Funktionsfähigkeit speichert die Anwendung Daten lokal in Ihrem
        Browser (kein Tracking, keine Werbung): Anmelde-Token, gewählter
        Anzeigename, Dark-Mode-Einstellung sowie die zuletzt gewählte
        Aussprache-Stimme. Diese Daten verbleiben auf Ihrem Gerät und werden mit
        dem Abmelden bzw. dem Leeren des Browserspeichers entfernt.
      </p>
      <ul>
        <li><strong>Rechtsgrundlage:</strong> Art. 6 Abs. 1 lit. f DSGVO bzw. § 25 Abs. 2 TTDSG (technisch erforderliche Speicherung)</li>
      </ul>
    </section>

    <section>
      <h2>10. Auftragsverarbeitung &amp; Drittlandtransfer</h2>
      <p>
        Als technischer Dienstleister wird Amazon Web Services eingesetzt
        (Cognito, S3, CloudFront, DynamoDB, Textract, Bedrock, Polly, Route 53).
        Die Verarbeitung erfolgt in Rechenzentren in der Europäischen Union
        (Frankfurt, eu-central-1). Mit dem Anbieter ist ein Vertrag zur
        Auftragsverarbeitung gemäß Art. 28 DSGVO abzuschließen.
      </p>
      <p class="note">
        Hinweis für den Betreiber: Bitte stellen Sie sicher, dass ein
        Auftragsverarbeitungsvertrag (AWS Data Processing Addendum) vorliegt.
        Soweit im Einzelfall eine Verarbeitung außerhalb der EU nicht
        ausgeschlossen werden kann, erfolgt diese auf Grundlage der
        EU-Standardvertragsklauseln.
      </p>
    </section>

    <section>
      <h2>11. Ihre Rechte</h2>
      <p>Ihnen stehen nach der DSGVO folgende Rechte zu:</p>
      <ul>
        <li>Auskunft (Art. 15 DSGVO)</li>
        <li>Berichtigung (Art. 16 DSGVO)</li>
        <li>Löschung (Art. 17 DSGVO)</li>
        <li>Einschränkung der Verarbeitung (Art. 18 DSGVO)</li>
        <li>Datenübertragbarkeit (Art. 20 DSGVO)</li>
        <li>Widerspruch (Art. 21 DSGVO)</li>
      </ul>
      <p>
        Zur Ausübung Ihrer Rechte wenden Sie sich an den oben genannten
        Verantwortlichen. Zudem haben Sie das Recht, sich bei einer
        Datenschutz-Aufsichtsbehörde zu beschweren.
      </p>
    </section>

    <section>
      <h2>12. Löschung des Kontos</h2>
      <p>
        Auf Anfrage beim Verantwortlichen wird Ihr Konto mit allen zugehörigen
        Daten (Vokabelsets, Fortschritt, Übungssitzungen, Liga-Mitgliedschaft)
        gelöscht. Automatische Löschfristen gelten wie in den jeweiligen
        Abschnitten angegeben.
      </p>
    </section>

    <section>
      <h2>13. Änderungen dieser Datenschutzerklärung</h2>
      <p>
        Wir passen diese Datenschutzerklärung an, sobald Änderungen an der
        Anwendung oder der Rechtslage dies erfordern. Es gilt die jeweils hier
        veröffentlichte, aktuelle Fassung.
      </p>
    </section>
  </div>
</template>

<script setup>
const lastUpdated = '28.08.2026'
</script>

<style scoped>
.prose-dsgvo section {
  @apply mb-8;
}
.prose-dsgvo h2 {
  @apply text-lg font-semibold text-gray-900 dark:text-white mb-2 mt-2;
}
.prose-dsgvo p {
  @apply text-gray-700 dark:text-gray-300 leading-relaxed mb-2;
}
.prose-dsgvo ul {
  @apply list-disc list-inside text-gray-700 dark:text-gray-300 space-y-1 mb-2;
}
.prose-dsgvo .placeholder {
  @apply p-3 bg-gray-50 dark:bg-gray-800 border border-dashed border-gray-300 dark:border-gray-600 rounded text-gray-700 dark:text-gray-300;
}
.prose-dsgvo .note {
  @apply text-sm text-gray-500 dark:text-gray-400 italic;
}
</style>
