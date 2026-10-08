#ifndef QUANTUM_FLEX_PQXX_COMPAT_HPP
#define QUANTUM_FLEX_PQXX_COMPAT_HPP

#include <string>

// Mitigate GCC 15 / libpqxx-7.10 duplicate weak-symbol dynamic initialization
// and double-free in tcache upon exit by declaring type_name as extern template.
namespace pqxx {
    template<typename TYPE>
    extern const std::string type_name;
}

#include <pqxx/pqxx>

#endif // QUANTUM_FLEX_PQXX_COMPAT_HPP
