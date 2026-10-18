// Which locales SpeechTranscriber and DictationTranscriber support on this Mac,
// which are installed, and the asset status of each. Read-only: never installs.
//   swiftc -parse-as-library -O probe_locales.swift -o /tmp/probe_locales && /tmp/probe_locales
import Foundation
import Speech

@main
struct Probe {
    static func main() async {
        print("SpeechTranscriber.isAvailable:", SpeechTranscriber.isAvailable)
        let sup = await SpeechTranscriber.supportedLocales
        let inst = await SpeechTranscriber.installedLocales
        print("SpeechTranscriber supported (\(sup.count)):", sup.map { $0.identifier(.bcp47) }.sorted().joined(separator: " "))
        print("SpeechTranscriber installed (\(inst.count)):", inst.map { $0.identifier(.bcp47) }.sorted().joined(separator: " "))
        let dsup = await DictationTranscriber.supportedLocales
        let dinst = await DictationTranscriber.installedLocales
        print("DictationTranscriber supported (\(dsup.count)):", dsup.map { $0.identifier(.bcp47) }.sorted().joined(separator: " "))
        print("DictationTranscriber installed (\(dinst.count)):", dinst.map { $0.identifier(.bcp47) }.sorted().joined(separator: " "))
        let want = ["en-US","en-GB","es-ES","es-MX","fr-FR","de-DE","it-IT","pt-BR","pt-PT","ca-ES","nl-NL","sv-SE","da-DK","nb-NO","pl-PL","cs-CZ","ru-RU","uk-UA","fi-FI","tr-TR","ko-KR","ja-JP","zh-CN","zh-TW","zh-HK","yue-CN"]
        for id in want {
            let loc = Locale(identifier: id)
            let eq = await SpeechTranscriber.supportedLocale(equivalentTo: loc)
            let t = SpeechTranscriber(locale: eq ?? loc, preset: .timeIndexedTranscriptionWithAlternatives)
            let st = await AssetInventory.status(forModules: [t])
            print(id, "-> equivalent:", eq?.identifier(.bcp47) ?? "nil", "status:", st)
        }
        print("maximumReservedLocales:", AssetInventory.maximumReservedLocales)
        print("reservedLocales:", await AssetInventory.reservedLocales.map { $0.identifier(.bcp47) })
    }
}
